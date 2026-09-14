"""
Integration test for the full pipeline across all demo samples.
"""
import unittest
from pathlib import Path
from src.config import DEMO_SAMPLES_DIR
from src.engine import get_kit_profile
from src.pipeline import run_pipeline


class TestFullPipeline(unittest.TestCase):

    def setUp(self):
        self.profile_alpha = get_kit_profile("SIM-PROFILE-ALPHA")
        self.profile_beta = get_kit_profile("SIM-PROFILE-BETA")

    def test_alpha_positive_sample(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_alpha_positive.jpg"
        with open(sample_path, "rb") as f:
            data = f.read()

        res = run_pipeline(
            image_bytes=data,
            profile=self.profile_alpha,
            operator_id="E2E-TEST-OP",
            persist=False
        )
        self.assertTrue(res.success)
        self.assertTrue(res.quality_report.passed)
        self.assertEqual(res.evidence_record.result, "Positive")

    def test_alpha_negative_sample(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_alpha_negative.jpg"
        with open(sample_path, "rb") as f:
            data = f.read()

        res = run_pipeline(
            image_bytes=data,
            profile=self.profile_alpha,
            operator_id="E2E-TEST-OP",
            persist=False
        )
        self.assertTrue(res.success)
        self.assertTrue(res.quality_report.passed)
        self.assertEqual(res.evidence_record.result, "Negative")

    def test_alpha_inconclusive_sample(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_alpha_inconclusive.jpg"
        with open(sample_path, "rb") as f:
            data = f.read()

        res = run_pipeline(
            image_bytes=data,
            profile=self.profile_alpha,
            operator_id="E2E-TEST-OP",
            persist=False
        )
        self.assertTrue(res.success)
        self.assertTrue(res.quality_report.passed)
        self.assertEqual(res.evidence_record.result, "Inconclusive")

    def test_beta_positive_sample(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_beta_positive.jpg"
        with open(sample_path, "rb") as f:
            data = f.read()

        res = run_pipeline(
            image_bytes=data,
            profile=self.profile_beta,
            operator_id="E2E-TEST-OP",
            persist=False
        )
        self.assertTrue(res.success)
        self.assertEqual(res.evidence_record.result, "Positive")

    def test_beta_negative_sample(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_beta_negative.jpg"
        with open(sample_path, "rb") as f:
            data = f.read()

        res = run_pipeline(
            image_bytes=data,
            profile=self.profile_beta,
            operator_id="E2E-TEST-OP",
            persist=False
        )
        self.assertTrue(res.success)
        self.assertEqual(res.evidence_record.result, "Negative")

    def test_blurry_rejection(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_blurry_rejection.jpg"
        with open(sample_path, "rb") as f:
            data = f.read()

        res = run_pipeline(
            image_bytes=data,
            profile=self.profile_alpha,
            persist=False
        )
        self.assertFalse(res.success)
        self.assertFalse(res.quality_report.blur_passed)
        self.assertIsNone(res.evidence_record)

    def test_glare_rejection(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_glare_rejection.jpg"
        with open(sample_path, "rb") as f:
            data = f.read()

        res = run_pipeline(
            image_bytes=data,
            profile=self.profile_alpha,
            persist=False
        )
        self.assertFalse(res.success)
        self.assertTrue(res.quality_report.glare_detected)
        self.assertIsNone(res.evidence_record)


if __name__ == "__main__":
    unittest.main()
