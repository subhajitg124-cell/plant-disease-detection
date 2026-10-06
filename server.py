"""
PatraDristi AI - Production API Server and Static Host
Provides REST API endpoints for CNN leaf disease classification and RAG advisory generation.
"""
import os
import sys
import io
import json
import base64
from typing import Any
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

pipeline_instance = None
try:
    from src.pipeline import PlantDiseasePipeline
    print("[INFO] Initializing PlantDiseasePipeline with PyTorch CNN & Vector RAG...")
    pipeline_instance = PlantDiseasePipeline(
        model_path=os.path.join(ROOT_DIR, "models", "plant_disease_cnn.pth"),
        class_mapping_path=os.path.join(ROOT_DIR, "data", "metadata", "plantvillage_class_mapping.csv"),
        kb_path=os.path.join(ROOT_DIR, "data", "knowledge_base", "agricultural_documents.json"),
        store_dir=os.path.join(ROOT_DIR, "models", "vector_index"),
        confidence_threshold=0.70
    )
    print("[INFO] PlantDiseasePipeline initialized successfully.")
except Exception as e:
    print(f"[WARNING] Could not initialize full pipeline: {e}")

class PatraDristiRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

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
                # Accept plant_hint from request body (supports both field names)
                plant_hint = (
                    data.get("plant_hint", "")
                    or data.get("sample_id", "").split("_")[0]
                ).lower()

                if pipeline_instance:
                    res = pipeline_instance.predict_and_advise(
                        img, plant_hint=plant_hint, filename=filename
                    )

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

                    response_payload = {
                        "plant": res.prediction.plant,
                        "disease": res.prediction.disease,
                        "canonical_id": res.prediction.canonical_id,
                        "confidence": float(res.confidence),
                        "status": res.status,
                        "user_message": res.user_message,
                        "advisory": advisory_dict,
                        "sources": res.sources
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
