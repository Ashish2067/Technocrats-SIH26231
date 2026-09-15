"""
Searchable Test History Repository for PS26231 MVP.
Manages persistent local storage of evidence records using SQLite.
Supports flexible querying by test ID, operator, profile, and result.
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.config import DATABASE_PATH, EVIDENCE_DIR, DEMO_SAMPLES_DIR, STANDARD_DISCLAIMER
from src.models import EvidenceRecord
from src.evidence import compute_image_sha256


def get_db_connection() -> sqlite3.Connection:
    """
    Creates and returns a connection to the SQLite database.
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """
    Initializes the SQLite schema and indexes.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_records (
                test_id TEXT PRIMARY KEY,
                timestamp_utc TEXT NOT NULL,
                timestamp_local TEXT NOT NULL,
                operator_id TEXT NOT NULL,
                kit_profile_id TEXT NOT NULL,
                kit_profile_name TEXT NOT NULL,
                result TEXT NOT NULL,
                image_sha256 TEXT NOT NULL,
                image_filename TEXT NOT NULL,
                gps_lat REAL,
                gps_lon REAL,
                record_json TEXT NOT NULL
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_operator ON test_records(operator_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_result ON test_records(result)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profile ON test_records(kit_profile_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON test_records(timestamp_utc DESC)")
        conn.commit()


def save_record(record: EvidenceRecord) -> bool:
    """
    Saves an EvidenceRecord to the database.
    """
    init_database()
    rec_dict = record.to_dict()
    json_str = json.dumps(rec_dict)

    lat = record.gps.get("latitude") if record.gps else None
    lon = record.gps.get("longitude") if record.gps else None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO test_records (
                test_id, timestamp_utc, timestamp_local, operator_id,
                kit_profile_id, kit_profile_name, result,
                image_sha256, image_filename, gps_lat, gps_lon, record_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.test_id,
            record.timestamp_utc,
            record.timestamp_local,
            record.operator_id,
            record.kit_profile.get("profile_id", "UNKNOWN"),
            record.kit_profile.get("name", "Unknown Profile"),
            record.result,
            record.image_sha256,
            record.image_filename,
            lat,
            lon,
            json_str
        ))
        conn.commit()
    return True


def get_record_by_id(test_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a single record by its Test ID.
    """
    init_database()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT record_json FROM test_records WHERE test_id = ?", (test_id,))
        row = cursor.fetchone()
        if row:
            return json.loads(row["record_json"])
    return None


def search_records(
    query: Optional[str] = None,
    result_filter: Optional[str] = None,
    profile_filter: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Searches and filters test records.
    `query` performs case-insensitive substring matching against test_id and operator_id.
    """
    init_database()
    conditions = []
    params = []

    if query and query.strip():
        q = f"%{query.strip()}%"
        conditions.append("(test_id LIKE ? OR operator_id LIKE ?)")
        params.extend([q, q])

    if result_filter and result_filter.strip() and result_filter.lower() != "all":
        conditions.append("result = ?")
        params.append(result_filter.strip())

    if profile_filter and profile_filter.strip() and profile_filter.lower() != "all":
        conditions.append("kit_profile_id = ?")
        params.append(profile_filter.strip())

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT record_json FROM test_records{where_clause} ORDER BY timestamp_utc DESC LIMIT ?"
    params.append(limit)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [json.loads(r["record_json"]) for r in rows]


def seed_demo_history_if_empty(force: bool = False) -> int:
    """
    Seeds curated baseline demonstration test records into SQLite if the database has no records.
    Ensures that Render deployments, fresh containers, and clean environments have reliable,
    tamper-evident demonstration audits available immediately upon boot.
    Returns the number of seeded records.
    """
    init_database()
    if not force:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM test_records")
            row = cursor.fetchone()
            if row and row["count"] > 0:
                return 0

    demo_definitions = [
        {
            "test_id": "TEST-DEMO-20260914-1015-01AP",
            "timestamp_utc": "2026-09-14T04:45:00+00:00",
            "timestamp_local": "2026-09-14 10:15:00",
            "operator_id": "DEMO-OFFICER-01",
            "profile_id": "SIM-PROFILE-ALPHA",
            "profile_name": "Simulated Field Kit Alpha (Purple Proxy)",
            "profile_version": "1.0-simulated",
            "sample_file": "sample_alpha_positive.jpg",
            "evidence_filename": "evidence_TEST-DEMO-20260914-1015-01AP.jpg",
            "result": "Positive",
            "color_analysis": {
                "raw_rgb": [144, 117, 138],
                "calibrated_rgb": [144, 117, 138],
                "calibrated_lab": [53.2, 14.8, -7.5],
                "delta_e_positive": 3.96,
                "delta_e_negative": 39.81
            },
            "gps": {
                "status": "available",
                "latitude": 28.6139,
                "longitude": 77.2090,
                "accuracy_meters": 4.5,
                "note": "Northern Sector Border Verification Post"
            }
        },
        {
            "test_id": "TEST-DEMO-20260914-1025-02AN",
            "timestamp_utc": "2026-09-14T04:55:00+00:00",
            "timestamp_local": "2026-09-14 10:25:00",
            "operator_id": "DEMO-OFFICER-02",
            "profile_id": "SIM-PROFILE-ALPHA",
            "profile_name": "Simulated Field Kit Alpha (Purple Proxy)",
            "profile_version": "1.0-simulated",
            "sample_file": "sample_alpha_negative.jpg",
            "evidence_filename": "evidence_TEST-DEMO-20260914-1025-02AN.jpg",
            "result": "Negative",
            "color_analysis": {
                "raw_rgb": [220, 200, 140],
                "calibrated_rgb": [220, 200, 140],
                "calibrated_lab": [81.5, -2.1, 35.4],
                "delta_e_positive": 43.84,
                "delta_e_negative": 4.59
            },
            "gps": {
                "status": "available",
                "latitude": 19.0760,
                "longitude": 72.8777,
                "accuracy_meters": 5.0,
                "note": "Western Maritime Inspection Checkpoint"
            }
        },
        {
            "test_id": "TEST-DEMO-20260914-1035-03AI",
            "timestamp_utc": "2026-09-14T05:05:00+00:00",
            "timestamp_local": "2026-09-14 10:35:00",
            "operator_id": "DEMO-OFFICER-01",
            "profile_id": "SIM-PROFILE-ALPHA",
            "profile_name": "Simulated Field Kit Alpha (Purple Proxy)",
            "profile_version": "1.0-simulated",
            "sample_file": "sample_alpha_inconclusive.jpg",
            "evidence_filename": "evidence_TEST-DEMO-20260914-1035-03AI.jpg",
            "result": "Inconclusive",
            "color_analysis": {
                "raw_rgb": [130, 120, 60],
                "calibrated_rgb": [130, 120, 60],
                "calibrated_lab": [50.8, -4.2, 36.1],
                "delta_e_positive": 36.31,
                "delta_e_negative": 21.07
            },
            "gps": {
                "status": "available",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "accuracy_meters": 6.2,
                "note": "Southern Air Transit Interdiction Bay"
            }
        },
        {
            "test_id": "TEST-DEMO-20260914-1045-04BP",
            "timestamp_utc": "2026-09-14T05:15:00+00:00",
            "timestamp_local": "2026-09-14 10:45:00",
            "operator_id": "DEMO-OFFICER-03",
            "profile_id": "SIM-PROFILE-BETA",
            "profile_name": "Simulated Field Kit Beta (Blue Proxy)",
            "profile_version": "1.0-simulated",
            "sample_file": "sample_beta_positive.jpg",
            "evidence_filename": "evidence_TEST-DEMO-20260914-1045-04BP.jpg",
            "result": "Positive",
            "color_analysis": {
                "raw_rgb": [113, 151, 189],
                "calibrated_rgb": [113, 151, 189],
                "calibrated_lab": [61.2, -4.8, -24.1],
                "delta_e_positive": 4.08,
                "delta_e_negative": 28.57
            },
            "gps": {
                "status": "available",
                "latitude": 22.5726,
                "longitude": 88.3639,
                "accuracy_meters": 3.8,
                "note": "Eastern River Freight Terminal"
            }
        },
        {
            "test_id": "TEST-DEMO-20260914-1055-05BN",
            "timestamp_utc": "2026-09-14T05:25:00+00:00",
            "timestamp_local": "2026-09-14 10:55:00",
            "operator_id": "DEMO-OFFICER-02",
            "profile_id": "SIM-PROFILE-BETA",
            "profile_name": "Simulated Field Kit Beta (Blue Proxy)",
            "profile_version": "1.0-simulated",
            "sample_file": "sample_beta_negative.jpg",
            "evidence_filename": "evidence_TEST-DEMO-20260914-1055-05BN.jpg",
            "result": "Negative",
            "color_analysis": {
                "raw_rgb": [230, 225, 215],
                "calibrated_rgb": [230, 225, 215],
                "calibrated_lab": [89.7, 0.4, 4.9],
                "delta_e_positive": 33.54,
                "delta_e_negative": 3.87
            },
            "gps": {
                "status": "available",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "accuracy_meters": 4.1,
                "note": "Coastal Customs Clearance Facility"
            }
        }
    ]

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    seeded_count = 0

    for demo in demo_definitions:
        sample_path = DEMO_SAMPLES_DIR / demo["sample_file"]
        dest_path = EVIDENCE_DIR / demo["evidence_filename"]

        if sample_path.is_file():
            img_bytes = sample_path.read_bytes()
            img_hash = compute_image_sha256(img_bytes)
            if not dest_path.is_file() or force:
                dest_path.write_bytes(img_bytes)
        else:
            img_hash = "0" * 64

        quality_report = {
            "passed": True,
            "blur_score": 175.0,
            "blur_passed": True,
            "exposure_status": "normal",
            "exposure_passed": True,
            "glare_detected": False,
            "glare_passed": True,
            "card_visible": True,
            "issues": []
        }

        record = EvidenceRecord(
            test_id=demo["test_id"],
            timestamp_utc=demo["timestamp_utc"],
            timestamp_local=demo["timestamp_local"],
            operator_id=demo["operator_id"],
            gps=demo["gps"],
            kit_profile={
                "profile_id": demo["profile_id"],
                "name": demo["profile_name"],
                "version": demo["profile_version"],
                "is_simulated": True
            },
            quality_report=quality_report,
            color_analysis=demo["color_analysis"],
            result=demo["result"],
            image_sha256=img_hash,
            image_filename=demo["evidence_filename"],
            disclaimer=STANDARD_DISCLAIMER
        )

        save_record(record)
        seeded_count += 1

    return seeded_count
