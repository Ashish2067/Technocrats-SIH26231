"""
Unit tests for Calibration and Deterministic Colour Science (src/calibration.py, src/color.py).
"""
import unittest
from src.calibration import compute_calibration_gains, apply_color_calibration
from src.color import rgb_to_cielab, calculate_delta_e00, compute_color_metrics


class TestColorAndCalibration(unittest.TestCase):

    def test_calibration_gain_computation(self):
        # Suppose white patch observed is warm yellowish (R=250, G=220, B=180)
        # Nominal target is (240, 240, 240)
        observed_white = (250.0, 220.0, 180.0)
        kr, kg, kb = compute_calibration_gains(observed_white, nominal_white_rgb=(240.0, 240.0, 240.0))
        
        # Red gain should be < 1.0 (reduce red)
        self.assertAlmostEqual(kr, 240.0 / 250.0, places=3)
        # Blue gain should be > 1.0 (boost blue)
        self.assertAlmostEqual(kb, 240.0 / 180.0, places=3)

    def test_apply_color_calibration(self):
        observed_reaction = (100.0, 100.0, 80.0)
        observed_white = (240.0, 240.0, 120.0)  # Heavy blue deficit
        calibrated_rgb, res = apply_color_calibration(observed_reaction, observed_white)
        
        self.assertTrue(res.success)
        # Blue should be boosted
        self.assertGreater(calibrated_rgb[2], observed_reaction[2])

    def test_rgb_to_cielab_bounds(self):
        # Pure White: L* should be ~100
        lab_white = rgb_to_cielab((255, 255, 255))
        self.assertAlmostEqual(lab_white[0], 100.0, delta=1.0)

        # Pure Black: L* should be ~0
        lab_black = rgb_to_cielab((0, 0, 0))
        self.assertAlmostEqual(lab_black[0], 0.0, delta=1.0)

    def test_delta_e_identical_colors(self):
        lab = [50.0, 20.0, -10.0]
        diff = calculate_delta_e00(lab, lab)
        self.assertAlmostEqual(diff, 0.0, delta=0.01)

    def test_delta_e_distinct_colors(self):
        lab_red = [53.2, 80.1, 67.2]
        lab_green = [87.7, -86.2, 83.2]
        diff = calculate_delta_e00(lab_red, lab_green)
        self.assertGreater(diff, 50.0)


if __name__ == "__main__":
    unittest.main()
