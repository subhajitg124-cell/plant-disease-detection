import os
import sys
import unittest
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.adaptation.adaptation_pipeline import FewShotAdaptationEngine
from scripts.adapt_unseen_dataset import run_unseen_adaptation_flow


class TestUnseenDatasetAdaptation(unittest.TestCase):

    def test_unseen_adaptation_flow_execution(self):
        output_report = "reports/test_unseen_results.json"
        res = run_unseen_adaptation_flow(output_report_path=output_report)

        self.assertIn("milestone", res)
        self.assertEqual(res["num_adapted_classes"], 4)
        self.assertGreaterEqual(res["adaptation_accuracy"], 0.80)
        self.assertTrue(os.path.exists(output_report))

        # Check sample diagnostic details
        diag = res["sample_unseen_diagnosis"]
        self.assertEqual(diag["status"], "supported")
        self.assertGreater(len(diag["treatment_steps"]), 0)

        if os.path.exists(output_report):
            os.remove(output_report)


if __name__ == "__main__":
    unittest.main()
