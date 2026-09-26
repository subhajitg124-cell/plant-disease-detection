import os
import sys
import json
import math
import re
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

HAS_FAISS = False
try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False

HAS_CHROMADB = False
try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


_PLANT_SLOTS = {
    'apple': 0, 'tomato': 1, 'potato': 2, 'grape': 3, 'corn': 4, 'maize': 4,
    'cherry': 5, 'peach': 6, 'pepper': 7, 'squash': 8, 'strawberry': 9,
    'orange': 10, 'citrus': 10, 'blueberry': 11, 'raspberry': 12, 'soybean': 13,
    'wheat': 14, 'rice': 15, 'cotton': 16, 'cucumber': 17, 'bean': 18
}

_DISEASE_SLOTS = {
    'scab': 30, 'black_rot': 31, 'cedar_apple_rust': 32, 'rust': 33, 'powdery_mildew': 34,
    'mildew': 35, 'cercospora': 36, 'gray_leaf_spot': 37, 'northern_leaf_blight': 38,
    'esca': 39, 'measles': 39, 'isariopsis': 40, 'haunglongbing': 41, 'greening': 41,
    'bacterial_spot': 42, 'early_blight': 43, 'late_blight': 44, 'leaf_scorch': 45,
    'leaf_mold': 46, 'mold': 46, 'septoria': 47, 'spider_mite': 48, 'mite': 48,
    'target_spot': 49, 'yellow_leaf_curl': 50, 'mosaic': 51, 'virus': 51,
    'blight': 52, 'rot': 53, 'spot': 54, 'canker': 55, 'anthracnose': 56
}

_STATUS_SLOTS = {
    'healthy': 70, 'vigorous': 71, 'diseased': 72, 'infected': 72
}

_SYMPTOM_SLOTS = {
    'spots': 80, 'rings': 81, 'concentric': 82, 'target': 82, 'pustules': 83,
    'lesion': 84, 'lesions': 84, 'discoloration': 85, 'defoliation': 86,
    'yellowing': 87, 'wilting': 88, 'stunting': 89, 'curling': 90, 'cupping': 90,
    'scorching': 91, 'webbing': 92, 'stippling': 93, 'scab': 94, 'scabs': 94,
    'watersoaked': 95, 'velvety': 96, 'olive': 97, 'mottled': 98, 'mottling': 98,
    'downy': 99, 'powdery': 100, 'shot': 101, 'mummies': 102, 'galls': 103,
    'halo': 104, 'necrosis': 105, 'chlorosis': 106
}

_TREATMENT_SLOTS = {
    'copper': 120, 'sulfur': 121, 'fungicide': 122, 'fungicides': 122, 'bactericide': 123,
    'neem': 124, 'mancozeb': 125, 'chlorothalonil': 126, 'myclobutanil': 127,
    'captan': 128, 'mefenoxam': 129, 'cymoxanil': 130, 'azoxystrobin': 131,
    'pruning': 132, 'prune': 132, 'mulch': 133, 'mulching': 133, 'rotation': 134,
    'biocontrol': 135, 'bacteriophage': 136, 'soap': 137, 'oil': 138, 'drip': 139,
    'trellis': 140, 'sanitation': 141
}

_CONDITION_SLOTS = {
    'humidity': 160, 'humid': 160, 'moisture': 161, 'wet': 162, 'rain': 163, 'rainy': 163,
    'warm': 164, 'cool': 165, 'hot': 166, 'dew': 167, 'overhead': 168, 'season': 169,
    'spring': 170, 'summer': 171, 'autumn': 172, 'winter': 173
}


class VectorStore:
    def __init__(self, dimension: int = 256, store_dir: str = "models/vector_index"):
        self.dimension = dimension
        self.store_dir = store_dir
        os.makedirs(self.store_dir, exist_ok=True)

        self.documents: List[Dict[str, Any]] = []
        self.embeddings: List[np.ndarray] = []
        self._canonical_index: Dict[str, int] = {}

        self.faiss_index = None
        if HAS_FAISS:
            self.faiss_index = faiss.IndexFlatIP(dimension)

        self.chroma_client = None
        self.chroma_collection = None
        if HAS_CHROMADB:
            try:
                self.chroma_client = chromadb.PersistentClient(
                    path=os.path.join(self.store_dir, "chroma")
                )
                self.chroma_collection = self.chroma_client.get_or_create_collection(
                    name="agricultural_kb"
                )
            except Exception as e:
                print(f"Warning: ChromaDB initialization fallback: {e}")
                self.chroma_client = None
                self.chroma_collection = None

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _text_to_vector(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dimension, dtype=np.float32)
        tokens = self._tokenize(text)
        if not tokens:
            return vec

        for idx, token in enumerate(tokens):
            pos_weight = 1.0 / (1.0 + 0.02 * idx)

            if token in _PLANT_SLOTS:
                slot = _PLANT_SLOTS[token]
                if slot < self.dimension:
                    vec[slot] += 4.0 * pos_weight

            if token in _DISEASE_SLOTS:
                slot = _DISEASE_SLOTS[token]
                if slot < self.dimension:
                    vec[slot] += 3.5 * pos_weight

            if token in _STATUS_SLOTS:
                slot = _STATUS_SLOTS[token]
                if slot < self.dimension:
                    vec[slot] += 3.0 * pos_weight

            if token in _SYMPTOM_SLOTS:
                slot = _SYMPTOM_SLOTS[token]
                if slot < self.dimension:
                    vec[slot] += 2.5 * pos_weight

            if token in _TREATMENT_SLOTS:
                slot = _TREATMENT_SLOTS[token]
                if slot < self.dimension:
                    vec[slot] += 2.0 * pos_weight

            if token in _CONDITION_SLOTS:
                slot = _CONDITION_SLOTS[token]
                if slot < self.dimension:
                    vec[slot] += 1.5 * pos_weight

            if idx > 0:
                prev = tokens[idx - 1]
                bigram = f"{prev}_{token}"
                if bigram in _DISEASE_SLOTS:
                    slot = _DISEASE_SLOTS[bigram]
                    if slot < self.dimension:
                        vec[slot] += 4.5 * pos_weight
                elif bigram in _SYMPTOM_SLOTS:
                    slot = _SYMPTOM_SLOTS[bigram]
                    if slot < self.dimension:
                        vec[slot] += 3.5 * pos_weight
                elif bigram in _TREATMENT_SLOTS:
                    slot = _TREATMENT_SLOTS[bigram]
                    if slot < self.dimension:
                        vec[slot] += 3.0 * pos_weight

            h = 5381
            for c in token:
                h = (((h << 5) + h) + ord(c)) & 0xFFFFFFFF
            dispersion_slot = 200 + (h % max(1, self.dimension - 200))
            if dispersion_slot < self.dimension:
                vec[dispersion_slot] += 0.3 * pos_weight

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def add_documents(
        self,
        docs: List[Dict[str, Any]],
        vectors: Optional[List[List[float]]] = None
    ):
        for i, doc in enumerate(docs):
            if vectors is not None and i < len(vectors):
                vec = np.array(vectors[i], dtype=np.float32)
            else:
                search_text = doc.get("search_text") or self._build_search_text(doc)
                vec = self._text_to_vector(search_text)

            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            doc_idx = len(self.documents)
            canonical_id = str(doc.get("canonical_id", f"doc_{doc_idx}"))

            self.documents.append(doc)
            self.embeddings.append(vec)
            self._canonical_index[canonical_id] = doc_idx

            if HAS_FAISS and self.faiss_index is not None:
                self.faiss_index.add(np.array([vec], dtype=np.float32))

            if self.chroma_collection is not None:
                try:
                    self.chroma_collection.upsert(
                        ids=[canonical_id],
                        embeddings=[vec.tolist()],
                        metadatas=[{
                            "canonical_id": canonical_id,
                            "plant": str(doc.get("plant", "")),
                            "disease": str(doc.get("disease", ""))
                        }],
                        documents=[doc.get("search_text", "")]
                    )
                except Exception:
                    pass

    def _build_search_text(self, doc: Dict[str, Any]) -> str:
        plant = doc.get("plant", "")
        disease = doc.get("disease", "")
        cid = doc.get("canonical_id", "")
        status = doc.get("health_status", "diseased")

        parts = [f"Plant: {plant}. Disease: {disease} (ID: {cid}). Status: {status}."]

        for field in ("symptoms", "causes", "risk_factors", "prevention", "management"):
            items = doc.get(field, [])
            if items:
                label = field.replace("_", " ").title()
                parts.append(f"{label}: {'; '.join(items)}.")

        return " ".join(parts)

    def search_by_vector(
        self, query_vector: Union[List[float], np.ndarray], top_k: int = 5
    ) -> List[Tuple[Dict[str, Any], float]]:
        if not self.embeddings:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec = q_vec / norm

        if HAS_FAISS and self.faiss_index is not None and self.faiss_index.ntotal > 0:
            k = min(top_k, self.faiss_index.ntotal)
            scores, indices = self.faiss_index.search(
                np.array([q_vec], dtype=np.float32), k
            )
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if 0 <= idx < len(self.documents):
                    results.append((self.documents[idx], float(score)))
            return results

        emb_matrix = np.array(self.embeddings, dtype=np.float32)
        sims = np.dot(emb_matrix, q_vec)
        k = min(top_k, len(self.documents))
        top_indices = np.argsort(sims)[::-1][:k]

        return [(self.documents[int(idx)], float(sims[idx])) for idx in top_indices]

    def search_by_query(
        self, query_text: str, top_k: int = 5, min_score: float = 0.0
    ) -> List[Tuple[Dict[str, Any], float]]:
        q_vec = self._text_to_vector(query_text)
        results = self.search_by_vector(q_vec, top_k=top_k)
        if min_score > 0.0:
            results = [(doc, score) for doc, score in results if score >= min_score]
        return results

    def search_by_canonical_id(self, canonical_id: str) -> Optional[Dict[str, Any]]:
        idx = self._canonical_index.get(canonical_id)
        if idx is not None:
            return self.documents[idx]
        for doc in self.documents:
            if doc.get("canonical_id") == canonical_id:
                return doc
        return None

    def search_by_plant(
        self, plant_name: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        name = plant_name.strip().lower()
        return [
            doc for doc in self.documents
            if doc.get("plant", "").lower() == name
        ][:top_k]

    def save_index(self, path: Optional[str] = None) -> str:
        target_path = path or os.path.join(self.store_dir, "vector_store.npz")
        docs_path = os.path.join(self.store_dir, "vector_documents.json")
        index_path = os.path.join(self.store_dir, "canonical_index.json")

        emb_matrix = (
            np.array(self.embeddings, dtype=np.float32)
            if self.embeddings
            else np.zeros((0, self.dimension))
        )
        np.savez_compressed(target_path, embeddings=emb_matrix)

        with open(docs_path, mode="w", encoding="utf-8") as f:
            json.dump(self.documents, f, indent=2)

        with open(index_path, mode="w", encoding="utf-8") as f:
            json.dump(self._canonical_index, f, indent=2)

        return target_path

    def load_index(self, path: Optional[str] = None) -> bool:
        target_path = path or os.path.join(self.store_dir, "vector_store.npz")
        docs_path = os.path.join(self.store_dir, "vector_documents.json")
        index_path = os.path.join(self.store_dir, "canonical_index.json")

        if not os.path.exists(target_path) or not os.path.exists(docs_path):
            return False

        data = np.load(target_path)
        loaded_embeddings = data["embeddings"]

        if loaded_embeddings.ndim == 2 and loaded_embeddings.shape[1] != self.dimension:
            print(
                f"Warning: Stored index dimension ({loaded_embeddings.shape[1]}) "
                f"does not match VectorStore dimension ({self.dimension}). "
                "Rebuilding index from source data."
            )
            return False

        with open(docs_path, mode="r", encoding="utf-8") as f:
            self.documents = json.load(f)

        if os.path.exists(index_path):
            with open(index_path, mode="r", encoding="utf-8") as f:
                raw = json.load(f)
                self._canonical_index = {k: int(v) for k, v in raw.items()}
        else:
            self._canonical_index = {
                str(doc.get("canonical_id", f"doc_{i}")): i
                for i, doc in enumerate(self.documents)
            }

        self.embeddings = [row for row in loaded_embeddings]

        if HAS_FAISS and self.faiss_index is not None and len(self.embeddings) > 0:
            self.faiss_index.reset()
            self.faiss_index.add(np.array(self.embeddings, dtype=np.float32))

        return True

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_documents": len(self.documents),
            "dimension": self.dimension,
            "has_faiss": HAS_FAISS,
            "has_chromadb": HAS_CHROMADB and self.chroma_collection is not None,
            "unique_plants": len({doc.get("plant") for doc in self.documents}),
            "unique_diseases": len({doc.get("canonical_id") for doc in self.documents}),
        }


if __name__ == "__main__":
    kb_path = "data/knowledge_base/agricultural_documents.json"
    if os.path.exists(kb_path):
        with open(kb_path, mode="r", encoding="utf-8") as f:
            docs = json.load(f)
        store = VectorStore(dimension=256)
        store.add_documents(docs)
        store.save_index()
        stats = store.get_stats()
        print(f"Indexed {stats['total_documents']} documents | {stats['unique_plants']} plants | dim={stats['dimension']}")

        results = store.search_by_query("apple scab olive spots fungal prevention", top_k=3)
        for doc, score in results:
            print(f"  [{score:.4f}] {doc['canonical_id']} — {doc['plant']} / {doc['disease']}")
