import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adaptation.adaptation_pipeline import FewShotAdaptationEngine, AdaptedClassProfile
from src.adaptation.baseline_freeze import BaselineFreezer
from src.contracts import PredictionStatus, IntegratedResponse
from tests.leaf_fixtures import make_textured_leaf


class TestAdaptationPipeline(unittest.TestCase):

    def setUp(self):
        self.engine = FewShotAdaptationEngine()

    def test_prototype_registration_and_classification(self):
        # Create 3 synthetic support samples for an unseen class "tea_blister_blight"
        support_imgs = [
            make_textured_leaf(224, 224, base=(30, 160, 40), seed=1),
            make_textured_leaf(224, 224, base=(35, 155, 45), seed=2),
            make_textured_leaf(224, 224, base=(32, 158, 42), seed=3)
        ]
        
        kb_meta = {
            "symptoms": ["Translucent circular blister spots on young tea leaves"],
            "causes": ["Exobasidium vexans obligate biotrophic fungus"],
            "prevention": ["Pruning to improve sunlight penetration", "Shade regulation"],
            "management": ["Copper oxychloride spray every 7-10 days"],
            "sources": ["UPASI Tea Research Institute"]
        }

        profile = self.engine.register_class_prototype(
            canonical_id="tea_blister_blight",
            plant="Tea",
            disease="Blister Blight",
            support_images=support_imgs,
            kb_metadata=kb_meta
        )

        self.assertEqual(profile.canonical_id, "tea_blister_blight")
        self.assertEqual(profile.num_support_samples, 3)
        self.assertEqual(len(profile.prototype_vector), 128)
        self.assertIn("tea_blister_blight", self.engine.prototypes)

        # Classify query image close to tea blister blight
        query_img = make_textured_leaf(224, 224, base=(33, 157, 43), seed=4)
        pred = self.engine.classify(query_img)

        self.assertEqual(pred.canonical_id, "tea_blister_blight")
        self.assertEqual(pred.plant, "Tea")
        self.assertEqual(pred.disease, "Blister Blight")
        self.assertGreaterEqual(pred.confidence, 0.60)
        self.assertEqual(pred.status, PredictionStatus.SUPPORTED.value)

    def test_adapted_predict_and_advise(self):
        # Register unseen class
        support_imgs = [make_textured_leaf(224, 224, base=(40, 150, 30), seed=10)]
        self.engine.register_class_prototype(
            canonical_id="coffee_rust",
            plant="Coffee",
            disease="Leaf Rust",
            support_images=support_imgs,
            kb_metadata={
                "symptoms": ["Yellow-orange powdery spots on underside of coffee leaves"],
                "causes": ["Hemileia vastatrix fungus"],
                "prevention": ["Resistant varieties (Castillo, Catimor)"],
                "management": ["Copper-based preventative fungicides"],
                "sources": ["World Coffee Research"]
            }
        )

        query_img = make_textured_leaf(224, 224, base=(40, 150, 30), seed=11)
        response = self.engine.predict_and_advise(query_img)

        self.assertIsInstance(response, IntegratedResponse)
        self.assertEqual(response.prediction.plant, "Coffee")
        self.assertEqual(response.prediction.disease, "Leaf Rust")
        self.assertIsNotNone(response.advisory)
        self.assertGreater(len(response.advisory.management), 0)
        self.assertIn("World Coffee Research", response.sources)

    def test_non_plant_rejection_in_adaptation(self):
        # Grey non-plant box should be rejected
        grey_img = np.full((224, 224, 3), 128, dtype=np.uint8)
        pred = self.engine.classify(grey_img)
        self.assertEqual(pred.status, PredictionStatus.NOT_A_PLANT.value)

    def test_baseline_freeze_manifest(self):
        freezer = BaselineFreezer(manifest_path="reports/test_baseline_manifest.json")
        manifest = freezer.generate_freeze_manifest()

        self.assertIn("baseline_version", manifest)
        self.assertIn("hyperparameters", manifest)
        self.assertIn("components", manifest)

        is_valid, mismatches = freezer.verify_integrity()
        self.assertTrue(is_valid)
        self.assertEqual(len(mismatches), 0)

        if os.path.exists("reports/test_baseline_manifest.json"):
            os.remove("reports/test_baseline_manifest.json")


if __name__ == "__main__":
    unittest.main()
