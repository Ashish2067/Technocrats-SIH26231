"""
Unit tests for Kit Profile Loading and Classification Engine (src/engine.py).
"""
import unittest
from src.engine import list_available_profiles, get_kit_profile, classify_result
from src.models import ColorMetrics


class TestEngine(unittest.TestCase):

    def setUp(self):
        self.profiles = list_available_profiles()
        self.profile_alpha = get_kit_profile("SIM-PROFILE-ALPHA")
        self.profile_beta = get_kit_profile("SIM-PROFILE-BETA")

    def test_profiles_loaded_and_marked_simulated(self):
        self.assertGreaterEqual(len(self.profiles), 2)
        self.assertIsNotNone(self.profile_alpha)
        self.assertIsNotNone(self.profile_beta)
        self.assertTrue(self.profile_alpha.is_simulated)
        self.assertTrue(self.profile_beta.is_simulated)
        self.assertIn("SIMULATED", self.profile_alpha.disclaimer)

    def test_classify_positive_result(self):
        # Target positive for Alpha is [26.5, 41.2, -36.4]
        # Very close to target: dE_pos = 1.0, dE_neg = 45.0
        metrics = ColorMetrics(
            raw_rgb=[95, 35, 120],
            calibrated_rgb=[95, 35, 120],
            calibrated_lab=[27.0, 41.0, -36.0],
            delta_e_positive=1.2,
            delta_e_negative=42.0
        )
        outcome, reason = classify_result(metrics, self.profile_alpha)
        self.assertEqual(outcome, "Positive")
        self.assertIn("matches positive proxy target", reason)

    def test_classify_negative_result(self):
        # Target negative for Alpha is [80.5, -2.1, 34.2]
        metrics = ColorMetrics(
            raw_rgb=[220, 200, 140],
            calibrated_rgb=[220, 200, 140],
            calibrated_lab=[80.0, -2.0, 34.0],
            delta_e_positive=45.0,
            delta_e_negative=1.5
        )
        outcome, reason = classify_result(metrics, self.profile_alpha)
        self.assertEqual(outcome, "Negative")
        self.assertIn("matches negative proxy target", reason)

    def test_classify_inconclusive_when_out_of_bounds(self):
        # Way out of bounds for both positive and negative
        metrics = ColorMetrics(
            raw_rgb=[0, 255, 0],
            calibrated_rgb=[0, 255, 0],
            calibrated_lab=[87.0, -86.0, 83.0],
            delta_e_positive=55.0,
            delta_e_negative=48.0
        )
        outcome, reason = classify_result(metrics, self.profile_alpha)
        self.assertEqual(outcome, "Inconclusive")
        self.assertIn("outside all expected profile boundaries", reason)

    def test_classify_inconclusive_when_ambiguous_margin(self):
        # dE_pos and dE_neg are both within 2.0 of each other (violating margin of 5.0)
        metrics = ColorMetrics(
            raw_rgb=[150, 150, 150],
            calibrated_rgb=[150, 150, 150],
            calibrated_lab=[55.0, 5.0, -5.0],
            delta_e_positive=11.0,
            delta_e_negative=12.5
        )
        outcome, reason = classify_result(metrics, self.profile_alpha)
        self.assertEqual(outcome, "Inconclusive")
        self.assertIn("Ambiguous reaction", reason)


if __name__ == "__main__":
    unittest.main()
