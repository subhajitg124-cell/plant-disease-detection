"""
Few-Shot Visual & RAG Adaptation Pipeline for Plant Disease Detection.

Provides dynamic adaptation capabilities to rapidly incorporate unseen crop species
and novel pathologies without full CNN retraining. Combines deep visual prototype
centroid embeddings with dynamic agricultural knowledge base registration.
"""

import os
import sys
import json
import csv
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.contracts import VisionPrediction, PredictionStatus, IntegratedResponse, AdvisoryResult
from src.embeddings.visual_embeddings import VisualEmbeddingExtractor
from src.retrieval.vector_store import VectorStore
from src.retrieval.rag_retriever import RAGRetriever
from src.advisory.advisory_generator import AdvisoryGenerator
from src.preprocessing.pipeline import PreprocessingPipeline


@dataclass
class AdaptedClassProfile:
    """Metadata profile for an adapted (previously unseen) class."""
    canonical_id: str
    plant: str
    disease: str
    num_support_samples: int = 0
    prototype_vector: List[float] = field(default_factory=list)
    symptoms: List[str] = field(default_factory=list)
    causes: List[str] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    prevention: List[str] = field(default_factory=list)
    management: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AdaptationResult:
    """Summary result of an adaptation session."""
    adapted_classes: List[str]
    num_total_classes: int
    mean_support_samples: float
    accuracy_on_query: Optional[float] = None
    macro_f1_on_query: Optional[float] = None
    adaptation_time_sec: float = 0.0
    status: str = "success"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FewShotAdaptationEngine:
    """
    Engine for rapid few-shot prototype adaptation and RAG dynamic registration.
    """

    def __init__(
        self,
        extractor: Optional[VisualEmbeddingExtractor] = None,
        vector_store: Optional[VectorStore] = None,
        retriever: Optional[RAGRetriever] = None,
        generator: Optional[AdvisoryGenerator] = None,
        confidence_threshold: float = 0.60
    ):
        self.extractor = extractor if extractor is not None else VisualEmbeddingExtractor()
        if retriever is not None:
            self.retriever = retriever
            self.vector_store = retriever.vector_store
        else:
            self.retriever = RAGRetriever()
            self.vector_store = vector_store if vector_store is not None else self.retriever.vector_store
            self.retriever.vector_store = self.vector_store

        self.generator = generator if generator is not None else AdvisoryGenerator(retriever=self.retriever)
        self.confidence_threshold = confidence_threshold
        self.preprocessing = PreprocessingPipeline(target_size=(224, 224))

        # Prototypes dictionary: {canonical_id: np.ndarray (128-d)}
        self.prototypes: Dict[str, np.ndarray] = {}
        self.class_profiles: Dict[str, AdaptedClassProfile] = {}

        # Initialize base 38 classes prototypes from embedding extractor cache if available
        self._init_base_prototypes()

    def _init_base_prototypes(self):
        """Initializes known canonical classes into prototype memory."""
        cache_path = "models/visual_embeddings_cache.npz"
        if os.path.exists(cache_path):
            try:
                data = np.load(cache_path, allow_pickle=True)
                embeddings = data["embeddings"]
                labels = data["labels"]
                unique_labels = np.unique(labels)
                for lbl in unique_labels:
                    mask = (labels == lbl)
                    class_embs = embeddings[mask]
                    centroid = np.mean(class_embs, axis=0)
                    norm = np.linalg.norm(centroid)
                    if norm > 0:
                        centroid = centroid / norm
                    cid_str = f"class_{lbl}"
                    self.prototypes[cid_str] = centroid
            except Exception as e:
                pass

    def register_class_prototype(
        self,
        canonical_id: str,
        plant: str,
        disease: str,
        support_images: List[Union[str, np.ndarray, Image.Image, List[float]]],
        kb_metadata: Optional[Dict[str, Any]] = None
    ) -> AdaptedClassProfile:
        """
        Computes prototype centroid for a new class and registers it in vector store & KB.
        """
        embeddings: List[np.ndarray] = []
        for item in support_images:
            if isinstance(item, list) and len(item) == self.extractor.embedding_dim:
                emb = np.array(item, dtype=np.float32)
            else:
                emb_list = self.extractor.extract(item)
                emb = np.array(emb_list, dtype=np.float32)

            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
            embeddings.append(emb)

        if not embeddings:
            # Fallback zero prototype if empty
            centroid = np.zeros(self.extractor.embedding_dim, dtype=np.float32)
        else:
            centroid = np.mean(embeddings, axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm

        self.prototypes[canonical_id] = centroid

        # Prepare KB profile
        meta = kb_metadata or {}
        profile = AdaptedClassProfile(
            canonical_id=canonical_id,
            plant=plant,
            disease=disease,
            num_support_samples=len(support_images),
            prototype_vector=centroid.tolist(),
            symptoms=meta.get("symptoms", [f"Observed visual symptoms on {plant} foliage corresponding to {disease}."]),
            causes=meta.get("causes", [f"Infection caused by {disease} pathology affecting {plant}."]),
            risk_factors=meta.get("risk_factors", ["Favorable humidity and leaf wetness."]),
            prevention=meta.get("prevention", ["Sanitation, crop rotation, and disease-free seeds."]),
            management=meta.get("management", ["Targeted cultural practices and approved agronomic applications."]),
            sources=meta.get("sources", ["Agricultural Extension Service & Plant Pathology Division"])
        )
        self.class_profiles[canonical_id] = profile

        # Dynamically inject into VectorStore
        doc_dict = {
            "canonical_id": canonical_id,
            "plant": plant,
            "disease": disease,
            "symptoms": profile.symptoms,
            "causes": profile.causes,
            "risk_factors": profile.risk_factors,
            "prevention": profile.prevention,
            "management": profile.management,
            "sources": profile.sources
        }
        self.vector_store.add_document(doc_dict)

        return profile

    def adapt_dataset(
        self,
        support_data: Dict[str, List[Union[str, np.ndarray, Image.Image]]],
        metadata_map: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> AdaptationResult:
        """
        Adapts the entire engine to an unseen dataset given support instances.
        """
        import time
        t0 = time.perf_counter()
        adapted_ids = []

        meta_map = metadata_map or {}
        for canonical_id, images in support_data.items():
            meta = meta_map.get(canonical_id, {})
            plant = meta.get("plant", canonical_id.split("_")[0].capitalize())
            disease = meta.get("disease", " ".join(canonical_id.split("_")[1:]).capitalize())
            self.register_class_prototype(
                canonical_id=canonical_id,
                plant=plant,
                disease=disease,
                support_images=images,
                kb_metadata=meta
            )
            adapted_ids.append(canonical_id)

        t1 = time.perf_counter()
        num_samples = [len(v) for v in support_data.values()]
        mean_k = float(np.mean(num_samples)) if num_samples else 0.0

        return AdaptationResult(
            adapted_classes=adapted_ids,
            num_total_classes=len(self.prototypes),
            mean_support_samples=round(mean_k, 2),
            adaptation_time_sec=round(t1 - t0, 4),
            status="success"
        )

    def classify(
        self,
        input_source: Union[str, Image.Image, np.ndarray, Any],
        candidate_classes: Optional[List[str]] = None
    ) -> VisionPrediction:
        """
        Few-shot prototype cosine similarity classifier.
        """
        # 1. Preprocessing & Foliage greenness check
        is_valid, tensor_data, meta = self.preprocessing.process_image(input_source, return_tensor=True)
        if not is_valid:
            status = PredictionStatus.NOT_A_PLANT.value
            if meta.get("reason") in ["empty_image", "corrupted", "decode_error"]:
                status = PredictionStatus.UNKNOWN.value
            return VisionPrediction(
                plant="Unknown",
                disease="Invalid Image / Non-Plant Object",
                canonical_id="invalid_input",
                confidence=0.0,
                status=status,
                raw_label="Rejected"
            )

        # 2. Extract visual embedding
        query_emb = np.array(self.extractor.extract(input_source), dtype=np.float32)
        norm = np.linalg.norm(query_emb)
        if norm > 0:
            query_emb = query_emb / norm

        if not self.prototypes:
            return VisionPrediction(
                plant="Unknown",
                disease="No Prototypes Registered",
                canonical_id="unknown",
                confidence=0.0,
                status=PredictionStatus.UNKNOWN.value
            )

        # 3. Compute cosine similarities to target prototypes
        target_dict = self.prototypes
        if candidate_classes is not None:
            target_dict = {k: v for k, v in self.prototypes.items() if k in candidate_classes}
            if not target_dict:
                target_dict = self.prototypes

        best_id = ""
        best_sim = -1.0

        for cid, proto in target_dict.items():
            sim = float(np.dot(query_emb, proto))
            if sim > best_sim:
                best_sim = sim
                best_id = cid

        # Scale cosine similarity [-1, 1] into [0, 1] confidence
        conf = max(0.0, min(1.0, (best_sim + 1.0) / 2.0))
        
        # If model has sharp prototype match, apply calibrated scaling
        if best_sim > 0.4:
            conf = min(0.99, best_sim * 1.1)

        profile = self.class_profiles.get(best_id)
        if profile:
            plant_name = profile.plant
            disease_name = profile.disease
        else:
            plant_name = best_id.split("_")[0].capitalize()
            disease_name = " ".join(best_id.split("_")[1:]).capitalize()

        status = PredictionStatus.SUPPORTED.value if conf >= self.confidence_threshold else PredictionStatus.UNCERTAIN.value

        return VisionPrediction(
            plant=plant_name,
            disease=disease_name,
            canonical_id=best_id,
            confidence=round(conf, 4),
            status=status,
            raw_label=best_id,
            embedding=query_emb.tolist(),
            model_version="few_shot_adapted_v1"
        )

    def predict_and_advise(
        self,
        input_source: Union[str, Image.Image, np.ndarray, Any],
        candidate_classes: Optional[List[str]] = None
    ) -> IntegratedResponse:
        """
        Runs adapted few-shot classification, RAG retrieval, and advisory generation.
        """
        prediction = self.classify(input_source, candidate_classes=candidate_classes)
        response = self.generator.generate_advisory(prediction)
        return response

    def evaluate_query_set(
        self,
        query_data: Dict[str, List[Union[str, np.ndarray, Image.Image]]],
        candidate_classes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Evaluates adaptation accuracy and metrics across query instances.
        """
        y_true = []
        y_pred = []
        total = 0
        correct = 0

        target_classes = candidate_classes if candidate_classes is not None else list(query_data.keys())
        class_to_idx = {k: i for i, k in enumerate(target_classes)}

        for true_cid, images in query_data.items():
            for img in images:
                total += 1
                pred = self.classify(img, candidate_classes=target_classes)
                y_true.append(class_to_idx.get(true_cid, 0))
                y_pred.append(class_to_idx.get(pred.canonical_id, -1))
                if pred.canonical_id == true_cid:
                    correct += 1

        acc = (correct / total) if total > 0 else 0.0

        # Compute per-class precision and recall
        from src.evaluation.metrics import calculate_metrics
        metrics = calculate_metrics(y_true, y_pred, num_classes=max(len(target_classes), 1))
        metrics["evaluation_total_samples"] = total
        metrics["evaluation_correct_samples"] = correct
        metrics["adaptation_accuracy"] = round(acc, 4)

        return metrics
