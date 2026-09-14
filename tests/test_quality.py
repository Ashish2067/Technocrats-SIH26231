"""
Unit tests for Image Quality Assessment (src/quality.py).
"""
import unittest
import cv2
import numpy as np
from src.quality import check_blur, check_exposure, check_glare, assess_image_quality
from src.config import DEMO_SAMPLES_DIR


class TestQualityAssessment(unittest.TestCase):

    def setUp(self):
        # Create a sharp test pattern
        self.sharp_img = np.zeros((300, 400), dtype=np.uint8)
        self.sharp_img[::20, :] = 255
        self.sharp_img[:, ::20] = 255

        # Create a blurred version
        self.blurred_img = cv2.GaussianBlur(self.sharp_img, (31, 31), 10.0)

    def test_sharp_image_passes_blur(self):
        passed, score = check_blur(self.sharp_img)
        self.assertTrue(passed)
        self.assertGreater(score, 75.0)

    def test_blurred_image_fails_blur(self):
        passed, score = check_blur(self.blurred_img)
        self.assertFalse(passed)
        self.assertLess(score, 75.0)

    def test_underexposed_image_fails_exposure(self):
        dark_img = np.full((200, 200), 10, dtype=np.uint8)
        passed, status, under_r, over_r = check_exposure(dark_img)
        self.assertFalse(passed)
        self.assertEqual(status, "underexposed")

    def test_overexposed_image_fails_exposure(self):
        bright_img = np.full((200, 200), 250, dtype=np.uint8)
        passed, status, under_r, over_r = check_exposure(bright_img)
        self.assertFalse(passed)
        self.assertEqual(status, "overexposed")

    def test_glare_detection(self):
        # Create image with glare spot
        bgr = np.full((200, 200, 3), (120, 120, 120), dtype=np.uint8)
        cv2.circle(bgr, (100, 100), 40, (255, 255, 255), -1)
        passed, detected, ratio = check_glare(bgr)
        self.assertTrue(detected)
        self.assertFalse(passed)

    def test_full_quality_rejection_on_demo_samples(self):
        # Load the generated blurry demo sample
        blurry_path = DEMO_SAMPLES_DIR / "sample_blurry_rejection.jpg"
        if blurry_path.exists():
            img = cv2.imread(str(blurry_path))
            report = assess_image_quality(img, card_detected=True)
            self.assertFalse(report.passed)
            self.assertIn("blurry", " ".join(report.issues).lower())


if __name__ == "__main__":
    unittest.main()
