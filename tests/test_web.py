"""
Integration tests for Flask Web Application and REST API (src/web/app.py).
"""
import unittest
import io
from pathlib import Path
from src.web.app import app
from src.config import DEMO_SAMPLES_DIR


class TestWebApp(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_index_page(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Field Companion", res.data)
        self.assertIn(b"SIMULATED", res.data)

    def test_history_page(self):
        res = self.client.get("/history")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Searchable Field Test History", res.data)

    def test_reference_card_page(self):
        res = self.client.get("/reference-card")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"PROTOTYPE REFERENCE CARD", res.data)

    def test_api_profiles(self):
        res = self.client.get("/api/profiles")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertGreaterEqual(len(data["profiles"]), 2)

    def test_api_analyze_valid_sample(self):
        sample_path = DEMO_SAMPLES_DIR / "sample_alpha_positive.jpg"
        with open(sample_path, "rb") as f:
            file_bytes = f.read()

        data = {
            "image": (io.BytesIO(file_bytes), "sample.jpg"),
            "profile_id": "SIM-PROFILE-ALPHA",
            "operator_id": "WEB-TESTER",
            "gps": '{"latitude": 28.61, "longitude": 77.20, "accuracy_meters": 5.0}'
        }

        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        res_json = res.get_json()
        self.assertTrue(res_json["success"])
        self.assertTrue(res_json["quality_report"]["passed"])
        self.assertEqual(res_json["evidence_record"]["result"], "Positive")
        self.assertEqual(res_json["evidence_record"]["operator_id"], "WEB-TESTER")

    def test_api_history(self):
        res = self.client.get("/api/history")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        self.assertIsInstance(data["records"], list)


if __name__ == "__main__":
    unittest.main()
