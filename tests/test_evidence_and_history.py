"""
Unit tests for Evidence Records, SHA-256 Hashing, and SQLite History (src/evidence.py, src/history.py).
"""
import unittest
import hashlib
from src.evidence import compute_image_sha256, verify_image_integrity, create_evidence_record
from src.history import save_record, get_record_by_id, search_records, init_database
from src.engine import get_kit_profile
from src.models import QualityReport, ColorMetrics


class TestEvidenceAndHistory(unittest.TestCase):

    def setUp(self):
        init_database()
        self.sample_bytes = b"SIMULATED_TEST_IMAGE_BYTES_123456"
        self.expected_hash = hashlib.sha256(self.sample_bytes).hexdigest()
        self.profile = get_kit_profile("SIM-PROFILE-ALPHA")

        self.quality = QualityReport(
            passed=True, blur_score=150.0, blur_passed=True,
            exposure_status="normal", exposure_passed=True,
            glare_detected=False, glare_passed=True, card_visible=True,
            issues=[]
        )
        self.metrics = ColorMetrics(
            raw_rgb=[95, 35, 120],
            calibrated_rgb=[95, 35, 120],
            calibrated_lab=[27.0, 41.0, -36.0],
            delta_e_positive=1.2,
            delta_e_negative=42.0
        )

    def test_sha256_computation_and_integrity(self):
        computed_hash = compute_image_sha256(self.sample_bytes)
        self.assertEqual(computed_hash, self.expected_hash)
        self.assertTrue(verify_image_integrity(self.sample_bytes, self.expected_hash))
        self.assertFalse(verify_image_integrity(b"tampered_bytes", self.expected_hash))

    def test_create_and_save_evidence_record(self):
        record = create_evidence_record(
            image_bytes=self.sample_bytes,
            result="Positive",
            profile=self.profile,
            quality=self.quality,
            color_metrics=self.metrics,
            operator_id="OFFICER-TEST-99",
            gps={"latitude": 28.61, "longitude": 77.20, "accuracy_meters": 4.5}
        )

        self.assertTrue(record.test_id.startswith("TEST-"))
        self.assertEqual(record.image_sha256, self.expected_hash)
        self.assertEqual(record.operator_id, "OFFICER-TEST-99")

        # Save to SQLite
        saved = save_record(record)
        self.assertTrue(saved)

        # Retrieve by ID
        retrieved = get_record_by_id(record.test_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved["test_id"], record.test_id)
        self.assertEqual(retrieved["result"], "Positive")
        self.assertEqual(retrieved["image_sha256"], self.expected_hash)

        # Search by operator
        results = search_records(query="OFFICER-TEST-99")
        self.assertGreaterEqual(len(results), 1)

        # Filter by result
        pos_results = search_records(result_filter="Positive")
        self.assertTrue(any(r["test_id"] == record.test_id for r in pos_results))

    def test_seed_demo_history_if_empty(self):
        from src.history import seed_demo_history_if_empty
        # Calling seed when records already exist should return 0
        seeded = seed_demo_history_if_empty(force=False)
        self.assertEqual(seeded, 0)

        # Force seeding should seed all 5 curated demonstration records
        forced_seeded = seed_demo_history_if_empty(force=True)
        self.assertEqual(forced_seeded, 5)

        # Verify seeded records exist in database
        demo_pos = get_record_by_id("TEST-DEMO-20260914-1015-01AP")
        self.assertIsNotNone(demo_pos)
        self.assertEqual(demo_pos["result"], "Positive")
        self.assertEqual(demo_pos["kit_profile"]["profile_id"], "SIM-PROFILE-ALPHA")
        self.assertEqual(demo_pos["operator_id"], "DEMO-OFFICER-01")

        demo_beta = get_record_by_id("TEST-DEMO-20260914-1045-04BP")
        self.assertIsNotNone(demo_beta)
        self.assertEqual(demo_beta["result"], "Positive")
        self.assertEqual(demo_beta["kit_profile"]["profile_id"], "SIM-PROFILE-BETA")


if __name__ == "__main__":
    unittest.main()
