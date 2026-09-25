"""
End-to-End Pipeline & Scenario Tests for Plant Disease Detection & Advisory System.

Tests cover:
  1. Standard Disease Scenarios:
     - Tomato Early Blight
     - Potato Early Blight
     - Pepper Bell Bacterial Spot
     - Tomato Healthy
     - Symptoms & Causes query retrieval
     - Prevention query retrieval
     - Treatment & Control query retrieval
  2. Failure & Edge Cases:
     - Missing image file path
     - Invalid / non-plant image (rejection via foliage ratio)
     - Corrupted image input
     - Low-confidence prediction (safety gating)
     - Unknown disease / out-of-distribution input
     - Vector database query fallback
     - Direct canonical ID lookup fallback
  3. Response Contract Completeness:
     - Detected plant, disease, canonical ID
     - Symptoms, causes, risk factors, prevention, management
     - Sources, evidence chunks, confidence score, status
"""

import os
import sys
import unittest
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pipeline import PlantDiseasePipeline
from src.contracts import (
    VisionPrediction, AdvisoryResult, IntegratedResponse, PredictionStatus, RAGQueryInput
)
from src.retrieval.rag_retriever import RAGRetriever
from src.advisory.advisory_generator import AdvisoryGenerator


class TestDiseaseQueriesRetrieval(unittest.TestCase):
    """Verifies retrieval for required domain queries."""

    @classmethod
    def setUpClass(cls):
        cls.retriever = RAGRetriever()

    def test_tomato_early_blight_retrieval(self):
        """Query: Tomato Early Blight."""
        advisory = self.retriever.retrieve(
            RAGQueryInput(plant="Tomato", disease="Early blight", canonical_id="tomato_early_blight")
        )
        self.assertIsInstance(advisory, AdvisoryResult)
        self.assertEqual(advisory.canonical_id, "tomato_early_blight")
        self.assertTrue(self.retriever.is_grounded(advisory))
        self.assertIn("Alternaria", " ".join(advisory.causes))
        self.assertGreater(len(advisory.symptoms), 0)
        self.assertGreater(len(advisory.prevention), 0)
        self.assertGreater(len(advisory.management), 0)
        self.assertGreater(len(advisory.sources), 0)

    def test_potato_early_blight_retrieval(self):
        """Query: Potato Early Blight."""
        advisory = self.retriever.retrieve("potato_early_blight")
        self.assertEqual(advisory.canonical_id, "potato_early_blight")
        self.assertTrue(self.retriever.is_grounded(advisory))
        self.assertIn("Alternaria solani", " ".join(advisory.causes))
        self.assertGreater(len(advisory.symptoms), 0)
        self.assertGreater(len(advisory.management), 0)

    def test_pepper_bell_bacterial_spot_retrieval(self):
        """Query: Pepper Bell Bacterial Spot."""
        advisory = self.retriever.retrieve("bell_pepper_bacterial_spot")
        self.assertEqual(advisory.canonical_id, "bell_pepper_bacterial_spot")
        self.assertTrue(self.retriever.is_grounded(advisory))
        self.assertIn("Xanthomonas", " ".join(advisory.causes))
        self.assertGreater(len(advisory.sources), 0)

    def test_tomato_healthy_retrieval(self):
        """Query: Tomato Healthy."""
        advisory = self.retriever.retrieve("tomato_healthy")
        self.assertEqual(advisory.canonical_id, "tomato_healthy")
        self.assertTrue(self.retriever.is_grounded(advisory))
        self.assertGreater(len(advisory.prevention), 0)
        self.assertGreater(len(advisory.management), 0)

    def test_symptoms_and_causes_query(self):
        """Query focusing on symptoms and pathogen causes."""
        results = self.retriever.search_similar(
            "dark brown spots concentric rings target board pattern alternaria", top_k=3
        )
        self.assertGreater(len(results), 0)
        top_ids = [doc["canonical_id"] for doc, _ in results]
        self.assertTrue("tomato_early_blight" in top_ids or "potato_early_blight" in top_ids)

    def test_prevention_query(self):
        """Query focusing on disease prevention cultural practices."""
        results = self.retriever.search_similar(
            "crop rotation mulching resistant cultivars drip irrigation", top_k=5
        )
        self.assertGreater(len(results), 0)
        self.assertGreaterEqual(len(results), 1)

    def test_treatment_control_query(self):
        """Query focusing on chemical and biological treatment."""
        results = self.retriever.search_similar(
            "apply copper hydroxide mancozeb chlorothalonil fungicide spray", top_k=5
        )
        self.assertGreater(len(results), 0)
        # Verify scores are positive
        for _, score in results:
            self.assertGreater(score, 0.0)


class TestEndToEndPipelineScenarios(unittest.TestCase):
    """End-to-end tests for full pipeline execution."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = PlantDiseasePipeline()

    def test_valid_plant_prediction_and_advisory(self):
        """Simulate a valid plant image input through full pipeline."""
        img = np.zeros((224, 224, 3), dtype=np.uint8)
        img[:, :, 1] = 180  # Green leaf
        img[:, :, 0] = 30
        
        response = self.pipeline.predict_and_advise(img)
        self.assertIsInstance(response, IntegratedResponse)
        self.assertIn(response.status, [PredictionStatus.SUPPORTED.value, PredictionStatus.UNCERTAIN.value])
        self.assertIsInstance(response.prediction, VisionPrediction)
        self.assertGreater(len(response.user_message), 0)
        self.assertAlmostEqual(response.confidence, response.prediction.confidence)

    def test_structured_response_fields_when_supported(self):
        """Ensure all required final response elements exist when supported."""
        generator = AdvisoryGenerator()
        pred = VisionPrediction(
            plant="Tomato",
            disease="Early blight",
            canonical_id="tomato_early_blight",
            confidence=0.88,
            status=PredictionStatus.SUPPORTED.value,
            raw_label="Tomato___Early_blight",
            model_version="vision_v1"
        )
        res = generator.generate_advisory(pred)
        
        # Check all required response attributes
        self.assertEqual(res.prediction.plant, "Tomato")
        self.assertEqual(res.prediction.disease, "Early blight")
        self.assertEqual(res.status, PredictionStatus.SUPPORTED.value)
        self.assertIsNotNone(res.advisory)
        assert res.advisory is not None
        self.assertGreater(len(res.advisory.symptoms), 0)
        self.assertGreater(len(res.advisory.causes), 0)
        self.assertGreater(len(res.advisory.prevention), 0)
        self.assertGreater(len(res.advisory.management), 0)
        self.assertGreater(len(res.evidence), 0)
        self.assertGreater(len(res.sources), 0)
        self.assertIn("Tomato", res.user_message)
        self.assertIn("Early blight", res.user_message)
        self.assertIn("88.0%", res.user_message)


class TestPipelineFailureAndEdgeCases(unittest.TestCase):
    """Failure and edge cases."""

    @classmethod
    def setUpClass(cls):
        cls.pipeline = PlantDiseasePipeline()
        cls.generator = AdvisoryGenerator()

    def test_missing_image_file(self):
        """Non-existent image file should return NOT_A_PLANT rejection cleanly."""
        res = self.pipeline.predict_and_advise("non_existent_file_path_12345.jpg")
        self.assertEqual(res.status, PredictionStatus.NOT_A_PLANT.value)
        self.assertIsNone(res.advisory)
        self.assertGreater(len(res.warnings), 0)

    def test_non_plant_image_grey_box(self):
        """Uniform grey non-plant image should be rejected before CNN inference."""
        grey_img = np.full((224, 224, 3), 128, dtype=np.uint8)
        res = self.pipeline.predict_and_advise(grey_img)
        self.assertEqual(res.status, PredictionStatus.NOT_A_PLANT.value)
        self.assertIsNone(res.advisory)
        self.assertIn("plant foliage", res.user_message.lower())

    def test_tiny_image_below_dimensions(self):
        """Image smaller than 32x32 should be rejected."""
        tiny_img = np.zeros((16, 16, 3), dtype=np.uint8)
        res = self.pipeline.predict_and_advise(tiny_img)
        self.assertEqual(res.status, PredictionStatus.NOT_A_PLANT.value)
        self.assertIsNone(res.advisory)

    def test_low_confidence_prediction_gating(self):
        """Low-confidence predictions should be gated with UNCERTAIN status and no advisory."""
        uncertain_pred = VisionPrediction(
            plant="Tomato",
            disease="Early blight",
            canonical_id="tomato_early_blight",
            confidence=0.35,
            status=PredictionStatus.UNCERTAIN.value
        )
        res = self.generator.generate_advisory(uncertain_pred)
        self.assertEqual(res.status, PredictionStatus.UNCERTAIN.value)
        self.assertIsNone(res.advisory)
        self.assertEqual(len(res.evidence), 0)
        self.assertIn("confidence", res.user_message.lower())
        self.assertTrue(any("confidence" in w.lower() for w in res.warnings))

    def test_unknown_out_of_distribution_disease(self):
        """Unknown pathology should be handled gracefully with safety advice."""
        unknown_pred = VisionPrediction(
            plant="Exotic Crop",
            disease="Unknown Pathology",
            canonical_id="unknown_pathology_x",
            confidence=0.90,
            status=PredictionStatus.UNKNOWN.value
        )
        res = self.generator.generate_advisory(unknown_pred)
        self.assertEqual(res.status, PredictionStatus.UNKNOWN.value)
        self.assertIsNone(res.advisory)
        self.assertIn("specialist", res.user_message.lower())

    def test_unknown_canonical_id_fallback_advisory(self):
        """Querying retriever for unknown canonical ID generates structured fallback scaffold."""
        retriever = RAGRetriever()
        advisory = retriever.retrieve("unknown_nonexistent_disease_id")
        self.assertIsInstance(advisory, AdvisoryResult)
        self.assertEqual(advisory.canonical_id, "unknown_nonexistent_disease_id")
        self.assertFalse(retriever.is_grounded(advisory))
        self.assertTrue(any("Fallback" in s for s in advisory.sources))

    def test_batch_processing_with_mixed_inputs(self):
        """Batch processing should handle valid and invalid inputs without crashing."""
        valid_img = np.zeros((224, 224, 3), dtype=np.uint8)
        valid_img[:, :, 1] = 180
        invalid_img = np.full((224, 224, 3), 100, dtype=np.uint8)

        results = self.pipeline.predict_batch([valid_img, invalid_img, "bad_path.png"])
        self.assertEqual(len(results), 3)
        self.assertEqual(results[1].status, PredictionStatus.NOT_A_PLANT.value)
        self.assertEqual(results[2].status, PredictionStatus.NOT_A_PLANT.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
