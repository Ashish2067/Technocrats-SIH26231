"""
End-to-End Judge Validation Suite for PS26231.
Simulates a user/judge exercising every requirement:
- Verifies UI routes: /, /history, /reference-card
- Exercises demo samples: Alpha Pos, Alpha Neg, Alpha Inc, Beta Pos, Blur Rejection, Glare Rejection
- Validates that real pipelines execute without shortcuts
- Verifies evidence records, SHA-256 hashes, GPS data, timestamps
- Verifies searchable SQLite history and filtering
- Verifies disclaimer presence
"""
import unittest
import io
import json
import hashlib
from src.web.app import app
from src.config import DEMO_SAMPLES_DIR, STANDARD_DISCLAIMER
from src.history import search_records, get_record_by_id


class TestE2EJudgeWorkflow(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_01_all_ui_routes_load_successfully(self):
        """Verify /, /history, and /reference-card load with 200 OK and proper headers."""
        routes = ["/", "/history", "/reference-card"]
        for route in routes:
            res = self.client.get(route)
            self.assertEqual(res.status_code, 200, f"Route {route} failed with status {res.status_code}")
            # Verify persistent disclaimer is rendered on every page
            self.assertIn(b"SIMULATED / PROXY", res.data)
            self.assertIn(b"Presumptive Field Testing", res.data)

    def test_02_alpha_positive_execution(self):
        """Exercise Alpha Positive sample through real pipeline."""
        sample_path = DEMO_SAMPLES_DIR / "sample_alpha_positive.jpg"
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        expected_hash = hashlib.sha256(img_bytes).hexdigest()

        data = {
            "image": (io.BytesIO(img_bytes), "sample_alpha_positive.jpg"),
            "profile_id": "SIM-PROFILE-ALPHA",
            "operator_id": "JUDGE-OP-01",
            "gps": json.dumps({"latitude": 19.0760, "longitude": 72.8777, "accuracy_meters": 3.5})
        }

        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        self.assertTrue(body["success"])
        self.assertTrue(body["quality_report"]["passed"])
        self.assertTrue(body["card_detected"])

        ev = body["evidence_record"]
        self.assertEqual(ev["result"], "Positive")
        self.assertEqual(ev["operator_id"], "JUDGE-OP-01")
        self.assertEqual(ev["image_sha256"], expected_hash)
        self.assertEqual(ev["gps"]["status"], "available")
        self.assertAlmostEqual(ev["gps"]["latitude"], 19.0760, places=4)
        self.assertEqual(ev["kit_profile"]["profile_id"], "SIM-PROFILE-ALPHA")
        self.assertTrue(ev["kit_profile"]["is_simulated"])
        self.assertIn("PRESUMPTIVE", ev["disclaimer"])

        # Check real calculated Delta E (not zero, not dummy)
        ca = ev["color_analysis"]
        self.assertLessEqual(ca["delta_e_positive"], 14.0)
        self.assertGreater(ca["delta_e_negative"], 20.0)

    def test_03_alpha_negative_execution(self):
        """Exercise Alpha Negative sample through real pipeline."""
        sample_path = DEMO_SAMPLES_DIR / "sample_alpha_negative.jpg"
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        expected_hash = hashlib.sha256(img_bytes).hexdigest()

        data = {
            "image": (io.BytesIO(img_bytes), "sample_alpha_negative.jpg"),
            "profile_id": "SIM-PROFILE-ALPHA",
            "operator_id": "JUDGE-OP-02",
            "gps": json.dumps({"status": "unavailable"})
        }

        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        self.assertTrue(body["success"])
        ev = body["evidence_record"]
        self.assertEqual(ev["result"], "Negative")
        self.assertEqual(ev["image_sha256"], expected_hash)
        self.assertEqual(ev["gps"]["status"], "unavailable")

        ca = ev["color_analysis"]
        self.assertLessEqual(ca["delta_e_negative"], 12.0)
        self.assertGreater(ca["delta_e_positive"], 20.0)

    def test_04_alpha_inconclusive_execution(self):
        """Exercise Alpha Inconclusive sample through real pipeline."""
        sample_path = DEMO_SAMPLES_DIR / "sample_alpha_inconclusive.jpg"
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        data = {
            "image": (io.BytesIO(img_bytes), "sample_alpha_inconclusive.jpg"),
            "profile_id": "SIM-PROFILE-ALPHA",
            "operator_id": "JUDGE-OP-03"
        }

        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        self.assertTrue(body["success"])
        ev = body["evidence_record"]
        self.assertEqual(ev["result"], "Inconclusive")

    def test_05_beta_positive_execution(self):
        """Exercise Beta Positive sample (Cobalt Blue) through real pipeline."""
        sample_path = DEMO_SAMPLES_DIR / "sample_beta_positive.jpg"
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        data = {
            "image": (io.BytesIO(img_bytes), "sample_beta_positive.jpg"),
            "profile_id": "SIM-PROFILE-BETA",
            "operator_id": "JUDGE-OP-04"
        }

        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        self.assertTrue(body["success"])
        ev = body["evidence_record"]
        self.assertEqual(ev["result"], "Positive")
        self.assertEqual(ev["kit_profile"]["profile_id"], "SIM-PROFILE-BETA")

    def test_06_blur_quality_rejection(self):
        """Exercise Blurry sample and verify automated rejection."""
        sample_path = DEMO_SAMPLES_DIR / "sample_blurry_rejection.jpg"
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        data = {
            "image": (io.BytesIO(img_bytes), "sample_blurry.jpg"),
            "profile_id": "SIM-PROFILE-ALPHA",
            "operator_id": "JUDGE-OP-05"
        }

        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        # Must reject: success is False, evidence_record is None
        self.assertFalse(body["success"])
        self.assertIsNone(body["evidence_record"])
        self.assertFalse(body["quality_report"]["blur_passed"])
        self.assertIn("blurry", body["reasoning"].lower())

    def test_07_glare_quality_rejection(self):
        """Exercise Glare sample and verify automated rejection."""
        sample_path = DEMO_SAMPLES_DIR / "sample_glare_rejection.jpg"
        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        data = {
            "image": (io.BytesIO(img_bytes), "sample_glare.jpg"),
            "profile_id": "SIM-PROFILE-ALPHA",
            "operator_id": "JUDGE-OP-06"
        }

        res = self.client.post("/api/analyze", data=data, content_type="multipart/form-data")
        self.assertEqual(res.status_code, 200)
        body = res.get_json()

        self.assertFalse(body["success"])
        self.assertIsNone(body["evidence_record"])
        self.assertTrue(body["quality_report"]["glare_detected"])
        self.assertIn("glare", body["reasoning"].lower())

    def test_08_search_and_filter_history(self):
        """Verify searching and filtering in SQLite history."""
        # 1. Search by operator
        res_op = self.client.get("/api/history?query=JUDGE-OP-01")
        self.assertEqual(res_op.status_code, 200)
        records_op = res_op.get_json()["records"]
        self.assertGreaterEqual(len(records_op), 1)
        self.assertTrue(all("JUDGE-OP-01" in r["operator_id"] for r in records_op))

        # 2. Filter by result Positive
        res_pos = self.client.get("/api/history?result=Positive")
        self.assertEqual(res_pos.status_code, 200)
        records_pos = res_pos.get_json()["records"]
        self.assertGreaterEqual(len(records_pos), 1)
        self.assertTrue(all(r["result"] == "Positive" for r in records_pos))

        # 3. Filter by profile Beta
        res_beta = self.client.get("/api/history?profile=SIM-PROFILE-BETA")
        self.assertEqual(res_beta.status_code, 200)
        records_beta = res_beta.get_json()["records"]
        self.assertGreaterEqual(len(records_beta), 1)
        self.assertTrue(all(r["kit_profile"]["profile_id"] == "SIM-PROFILE-BETA" for r in records_beta))

    def test_09_reference_card_usable_by_detector(self):
        """Verify prototype reference card image is detectable by the detection engine."""
        import cv2
        from src.detection import detect_prototype_card

        card_path = DEMO_SAMPLES_DIR / "prototype_reference_card.jpg"
        img = cv2.imread(str(card_path))
        card = detect_prototype_card(img)

        self.assertTrue(card.found)
        self.assertIn("white", card.patches_rgb)
        self.assertIn("gray", card.patches_rgb)
        self.assertIn("black", card.patches_rgb)
        self.assertIn("reference_blue", card.patches_rgb)


if __name__ == "__main__":
    unittest.main()
