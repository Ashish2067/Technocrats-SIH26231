"""
Searchable Test History Repository for PS26231 MVP.
Manages persistent local storage of evidence records using SQLite.
Supports flexible querying by test ID, operator, profile, and result.
"""
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.config import DATABASE_PATH
from src.models import EvidenceRecord


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
