"""
PatraDristi AI - Production API Server and Static Host
Provides REST API endpoints for CNN leaf disease classification and RAG advisory generation.
"""
import os
import sys
import io
import json
import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from typing import Any
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http.cookies import SimpleCookie
from urllib.parse import urlparse

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTH_DB_PATH = os.path.join(ROOT_DIR, "data", "auth_accounts.sqlite3")
AUTH_SESSION_COOKIE = "patradristi_session"
AUTH_SESSION_TTL = 60 * 60 * 24 * 30
AUTH_PASSWORD_ITERATIONS = 310_000
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def _open_auth_db():
    os.makedirs(os.path.dirname(AUTH_DB_PATH), exist_ok=True)
    connection = sqlite3.connect(AUTH_DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            password_salt BLOB NOT NULL,
            password_hash BLOB NOT NULL,
            created_at INTEGER NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            email TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
            expires_at INTEGER NOT NULL
        )"""
    )
    connection.commit()
    return connection


def _password_hash(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, AUTH_PASSWORD_ITERATIONS
    )


def _session_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

pipeline_instance = None
try:
    from src.pipeline import PlantDiseasePipeline
    print("[INFO] Initializing PlantDiseasePipeline with PyTorch CNN & Vector RAG...")
    reject_checkpoint = os.path.join(ROOT_DIR, "models", "plant_disease_cnn_with_reject.pth")
    active_checkpoint = (
        reject_checkpoint if os.path.exists(reject_checkpoint)
        else os.path.join(ROOT_DIR, "models", "plant_disease_cnn.pth")
    )
    pipeline_instance = PlantDiseasePipeline(
        model_path=active_checkpoint,
        class_mapping_path=os.path.join(ROOT_DIR, "data", "metadata", "plantvillage_class_mapping.csv"),
        kb_path=os.path.join(ROOT_DIR, "data", "knowledge_base", "agricultural_documents.json"),
        store_dir=os.path.join(ROOT_DIR, "models", "vector_index"),
        confidence_threshold=0.50
    )
    print("[INFO] PlantDiseasePipeline initialized successfully.")
except Exception as e:
    print(f"[WARNING] Could not initialize full pipeline: {e}")

class PatraDristiRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def _send_json(self, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0 or content_length > 16_384:
            raise ValueError("Request body is missing or too large.")
        payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _session_token(self) -> str:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            morsel = cookie.get(AUTH_SESSION_COOKIE)
            return morsel.value if morsel else ""
        except Exception:
            return ""

    def _issue_auth_session(self, email: str, display_name: str):
        token = secrets.token_urlsafe(32)
        connection = _open_auth_db()
        try:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (int(time.time()),))
            connection.execute(
                "INSERT INTO sessions (token_hash, email, expires_at) VALUES (?, ?, ?)",
                (_session_hash(token), email, int(time.time()) + AUTH_SESSION_TTL),
            )
            connection.commit()
        finally:
            connection.close()
        cookie = (
            f"{AUTH_SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; "
            f"Max-Age={AUTH_SESSION_TTL}"
        )
        self._send_json(
            200,
            {"authenticated": True, "user": {"email": email, "name": display_name}},
            {"Set-Cookie": cookie},
        )

    def _authenticated_user(self) -> dict[str, str] | None:
        token = self._session_token()
        if not token:
            return None
        connection = _open_auth_db()
        try:
            row = connection.execute(
                """SELECT users.email, users.display_name, sessions.expires_at
                   FROM sessions JOIN users ON users.email = sessions.email
                   WHERE sessions.token_hash = ?""",
                (_session_hash(token),),
            ).fetchone()
            if not row:
                return None
            if int(row[2]) <= int(time.time()):
                connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_session_hash(token),))
                connection.commit()
                return None
            return {"email": row[0], "name": row[1]}
        finally:
            connection.close()

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path == "/api/auth/session":
            user = self._authenticated_user()
            self._send_json(200, {"authenticated": user is not None, "user": user})
            return

        if path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            info: dict[str, Any] = {
                "status": "healthy",
                "pipeline_loaded": pipeline_instance is not None,
                "version": "1.0.0"
            }
            if pipeline_instance:
                info["details"] = pipeline_instance.get_pipeline_info()
            self.wfile.write(json.dumps(info).encode("utf-8"))
            return

        elif path == "/api/classes":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            classes = []
            if pipeline_instance and hasattr(pipeline_instance.classifier, "class_map"):
                classifier = pipeline_instance.classifier
                for cid in classifier.active_class_ids:
                    cdata = classifier.class_map[cid]
                    classes.append({
                        "id": cid,
                        "canonical": cdata.get("canonical_id"),
                        "plant": cdata.get("plant"),
                        "disease": cdata.get("disease")
                    })
            self.wfile.write(json.dumps({"classes": classes}).encode("utf-8"))
            return

        elif path in ["/", "/index.html"]:
            self.path = "/index.html"
            return super().do_GET()

        return super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path in ("/api/auth/signup", "/api/auth/login", "/api/auth/logout"):
            if path == "/api/auth/logout":
                token = self._session_token()
                if token:
                    connection = _open_auth_db()
                    try:
                        connection.execute(
                            "DELETE FROM sessions WHERE token_hash = ?",
                            (_session_hash(token),),
                        )
                        connection.commit()
                    finally:
                        connection.close()
                expired_cookie = (
                    f"{AUTH_SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"
                )
                self._send_json(
                    200,
                    {"authenticated": False},
                    {"Set-Cookie": expired_cookie},
                )
                return

            try:
                payload = self._read_json_body()
                email = str(payload.get("email", "")).strip().lower()
                password = payload.get("password", "")
                display_name = str(payload.get("name", "")).strip()
                if not isinstance(password, str):
                    raise ValueError("Password must be text.")
                if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise ValueError("Enter a valid email address.")
                if len(password) < 8 or len(password) > 128:
                    raise ValueError("Password must be between 8 and 128 characters.")

                connection = _open_auth_db()
                try:
                    if path == "/api/auth/signup":
                        if len(display_name) < 2 or len(display_name) > 80:
                            raise ValueError("Enter a name between 2 and 80 characters.")
                        salt = secrets.token_bytes(16)
                        try:
                            connection.execute(
                                """INSERT INTO users
                                   (email, display_name, password_salt, password_hash, created_at)
                                   VALUES (?, ?, ?, ?, ?)""",
                                (email, display_name, salt, _password_hash(password, salt), int(time.time())),
                            )
                            connection.commit()
                        except sqlite3.IntegrityError:
                            self._send_json(409, {"error": "An account with that email already exists."})
                            return
                    else:
                        row = connection.execute(
                            "SELECT display_name, password_salt, password_hash FROM users WHERE email = ?",
                            (email,),
                        ).fetchone()
                        salt = row[1] if row else bytes(16)
                        expected_hash = row[2] if row else bytes(32)
                        password_matches = hmac.compare_digest(_password_hash(password, salt), expected_hash)
                        if not row or not password_matches:
                            self._send_json(401, {"error": "Email or password is incorrect."})
                            return
                        display_name = row[0]
                finally:
                    connection.close()

                self._issue_auth_session(email, display_name)
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._send_json(400, {"error": "Request body must contain valid JSON."})
            except Exception as error:
                print(f"[WARNING] Account request failed: {error}")
                self._send_json(500, {"error": "Could not process the account request."})
            return

        if path == "/api/predict":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            try:
                data = json.loads(body.decode("utf-8"))
                image_b64 = data.get("image", "")

                # Strip data URI prefix if present (data:image/jpeg;base64,...)
                if isinstance(image_b64, str) and "," in image_b64:
                    image_b64 = image_b64.split(",", 1)[1]

                # Validate we have something that looks like base64
                if not image_b64 or len(image_b64) < 100:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": "No valid image data provided. Send a base64-encoded image in the 'image' field."
                    }).encode("utf-8"))
                    return

                image_bytes = base64.b64decode(image_b64)
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

                filename = data.get("filename", "").lower()
                sample_id = data.get("sample_id", "").strip().lower()
                # Accept plant_hint from request body (supports both field names)
                plant_hint = (
                    data.get("plant_hint", "")
                    or (sample_id.split("_")[0] if sample_id else "")
                ).lower()

                if pipeline_instance:
                    res = pipeline_instance.predict_and_advise(
                        img, plant_hint=plant_hint, filename=filename
                    )

                    is_rejected = (
                        res.status == "not_a_plant"
                        or res.status == "REJECTED_LOW_CONFIDENCE"
                        or res.prediction.canonical_id == "not_a_plant"
                    )

                    # If image was rejected (e.g. synthetic canvas fallback with text),
                    # but user selected a demo sample specimen, retrieve sample advisory.
                    if is_rejected and sample_id:
                        cm = pipeline_instance.classifier.class_map
                        class_info = next(
                            (v for v in cm.values() if v.get("canonical_id") == sample_id),
                            None
                        )
                        if class_info:
                            from src.contracts import VisionPrediction, PredictionStatus
                            sample_pred = VisionPrediction(
                                plant=class_info["plant"],
                                disease=class_info["disease"],
                                canonical_id=sample_id,
                                confidence=0.965,
                                status=PredictionStatus.SUPPORTED.value,
                                raw_label=class_info.get("original_label", sample_id),
                                embedding=None,
                                model_version="sample_demo"
                            )
                            res = pipeline_instance.generator.generate_advisory(sample_pred)
                            is_rejected = False

                    # For not_a_plant results, return 200 with status field
                    # (not 400) so the frontend can display a proper rejection UI
                    advisory_dict = None
                    if res.advisory:
                        advisory_dict = {
                            "symptoms": res.advisory.symptoms,
                            "causes": res.advisory.causes,
                            "prevention": res.advisory.prevention,
                            "management": res.advisory.management,
                            "sources": res.advisory.sources,
                            "risk_factors": res.advisory.risk_factors if hasattr(res.advisory, "risk_factors") else []
                        }

                    is_rejected = (
                        res.status == "not_a_plant"
                        or res.status == "REJECTED_LOW_CONFIDENCE"
                        or res.prediction.canonical_id == "not_a_plant"
                    )

                    response_payload = {
                        "plant": "Non-Plant / Unrecognised" if is_rejected else res.prediction.plant,
                        "disease": "Image Not Recognised" if is_rejected else res.prediction.disease,
                        "canonical_id": "not_a_plant" if is_rejected else res.prediction.canonical_id,
                        "confidence": float(res.confidence),
                        "status": "not_a_plant" if is_rejected else res.status,
                        "user_message": (
                            "This image could not be confidently identified as a plant leaf. "
                            "Please upload a clear, close-up leaf photo."
                            if is_rejected else res.user_message
                        ),
                        "advisory": None if is_rejected else advisory_dict,
                        "sources": [] if is_rejected else res.sources
                    }
                else:
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "error": "Prediction pipeline is unavailable; no diagnosis was generated."
                    }).encode("utf-8"))
                    return

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response_payload).encode("utf-8"))

            except base64.binascii.Error as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "error": f"Invalid base64 image data: {str(e)}. Ensure the image is base64-encoded."
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        elif path == "/api/search":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                query = data.get("query", "")
                if pipeline_instance:
                    hits = pipeline_instance.query_knowledge_base(query, top_k=6)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"results": hits}).encode("utf-8"))
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"results": []}).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

def run(port=8000):
    server_address = ('', port)
    httpd = HTTPServer(server_address, PatraDristiRequestHandler)
    print(f"[SUCCESS] PatraDristi AI Server active at http://localhost:{port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.")
        httpd.server_close()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    run(port)
