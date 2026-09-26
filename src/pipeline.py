import os
from typing import Optional, List, Dict, Any, Union

import numpy as np

try:
    from PIL import Image
except ImportError:
    Image = None

from src.contracts import VisionPrediction, AdvisoryResult, IntegratedResponse, PredictionStatus
from src.vision.classifier import PlantDiseaseClassifier
from src.retrieval.rag_retriever import RAGRetriever
from src.advisory.advisory_generator import AdvisoryGenerator


class PlantDiseasePipeline:
    def __init__(
        self,
        model_path: Optional[str] = "models/plant_disease_cnn.pth",
        class_mapping_path: str = "data/metadata/plantvillage_class_mapping.csv",
        kb_path: str = "data/knowledge_base/agricultural_documents.json",
        store_dir: str = "models/vector_index",
        confidence_threshold: float = 0.60,
        device: Optional[str] = None
    ):
        self.classifier = PlantDiseaseClassifier(
            model_path=model_path,
            class_mapping_path=class_mapping_path,
            confidence_threshold=confidence_threshold,
            device=device
        )
        self.retriever = RAGRetriever(kb_path=kb_path, store_dir=store_dir)
        self.generator = AdvisoryGenerator(retriever=self.retriever)

    def predict_and_advise(
        self,
        image_input: Union[str, "Image.Image", np.ndarray],
        extract_embedding: bool = False
    ) -> IntegratedResponse:
        prediction = self.classifier.predict(
            image_input, extract_embedding=extract_embedding
        )
        response = self.generator.generate_advisory(prediction)
        return response

    def predict_batch(
        self,
        image_inputs: List[Union[str, "Image.Image", np.ndarray]],
    ) -> List[IntegratedResponse]:
        results: List[IntegratedResponse] = []
        for img in image_inputs:
            try:
                res = self.predict_and_advise(img)
            except Exception as exc:
                err_prediction = VisionPrediction(
                    plant="Error",
                    disease="Processing Error",
                    canonical_id="pipeline_error",
                    confidence=0.0,
                    status=PredictionStatus.NOT_A_PLANT.value
                )
                res = IntegratedResponse(
                    prediction=err_prediction,
                    advisory=None,
                    user_message=f"Pipeline error during processing: {exc}",
                    confidence=0.0,
                    status=PredictionStatus.NOT_A_PLANT.value,
                    evidence=[],
                    sources=[],
                    warnings=[f"Exception: {exc}"]
                )
            results.append(res)
        return results

    def classify_only(
        self,
        image_input: Union[str, "Image.Image", np.ndarray],
        extract_embedding: bool = False
    ) -> VisionPrediction:
        return self.classifier.predict(image_input, extract_embedding=extract_embedding)

    def query_knowledge_base(
        self,
        query_text: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        results = self.retriever.search_similar(query_text, top_k=top_k)
        return [
            {
                "canonical_id": doc.get("canonical_id"),
                "plant": doc.get("plant"),
                "disease": doc.get("disease"),
                "similarity_score": round(score, 4),
                "symptoms": doc.get("symptoms", []),
                "management": doc.get("management", []),
                "sources": doc.get("sources", [])
            }
            for doc, score in results
        ]

    def get_advisory_by_id(self, canonical_id: str) -> AdvisoryResult:
        return self.retriever.retrieve_by_canonical_id(canonical_id)

    def get_pipeline_info(self) -> Dict[str, Any]:
        kb_stats = self.retriever.get_kb_stats()
        return {
            "classifier": {
                "model_path": self.classifier.model_path,
                "num_classes": self.classifier.num_classes,
                "confidence_threshold": self.classifier.confidence_threshold,
                "device": str(self.classifier.device)
            },
            "knowledge_base": kb_stats,
            "pipeline_version": "1.0.0"
        }


if __name__ == "__main__":
    print("Initialising Plant Disease Pipeline...")
    pipeline = PlantDiseasePipeline()

    info = pipeline.get_pipeline_info()
    print(f"\nPipeline Info:")
    print(f"  Classifier: {info['classifier']['num_classes']} classes, device={info['classifier']['device']}")
    print(f"  Knowledge Base: {info['knowledge_base']['total_documents']} documents indexed")

    green_leaf = np.zeros((224, 224, 3), dtype=np.uint8)
    green_leaf[:, :, 1] = 190
    green_leaf[:, :, 0] = 30
    result = pipeline.predict_and_advise(green_leaf)
    print(f"  Status: {result.status}")
    print(f"  Confidence: {result.confidence:.3f}")
    print(f"  Plant/Disease: {result.prediction.plant} / {result.prediction.disease}")
    print(f"  Evidence chunks: {len(result.evidence)}")
    print(f"  Sources: {result.sources}")
    print(f"  Message: {result.user_message[:150]}...")

    adv = pipeline.get_advisory_by_id("tomato_early_blight")
    print(f"  Symptoms: {adv.symptoms[:2]}")
    print(f"  Management: {adv.management[:2]}")
    print(f"  Sources: {adv.sources}")

    hits = pipeline.query_knowledge_base("apple scab olive green spots fungal treatment", top_k=3)
    for hit in hits:
        print(f"  [{hit['similarity_score']}] {hit['canonical_id']} — {hit['plant']}/{hit['disease']}")

    print("\nPipeline end-to-end test complete.")
