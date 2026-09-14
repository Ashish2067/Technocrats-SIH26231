"""
Digital Evidence Record & Integrity module for PS26231 MVP.
Generates structured evidence records and calculates SHA-256 cryptographic hashes
over original image bytes to provide a tamper-evident audit record.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from src.config import EVIDENCE_DIR, STANDARD_DISCLAIMER
from src.models import (
    EvidenceRecord,
    KitProfile,
    QualityReport,
    ColorMetrics
)


def compute_image_sha256(image_bytes: bytes) -> str:
    """
    Computes the standard SHA-256 cryptographic hash of raw image bytes.
    Used as the integrity verification mechanism.
    """
    return hashlib.sha256(image_bytes).hexdigest()


def verify_image_integrity(image_bytes: bytes, expected_hash: str) -> bool:
    """
    Verifies that the provided image bytes match the recorded SHA-256 hash.
    """
    return compute_image_sha256(image_bytes).lower() == expected_hash.lower()


def generate_test_id() -> str:
    """
    Generates a human-readable, unique Test ID.
    Format: TEST-YYYYMMDD-HHMMSS-XXXX
    """
    now = datetime.now()
    unique_suffix = uuid.uuid4().hex[:4].upper()
    return f"TEST-{now.strftime('%Y%m%d-%H%M%S')}-{unique_suffix}"


def create_evidence_record(
    image_bytes: bytes,
    result: str,
    profile: KitProfile,
    quality: QualityReport,
    color_metrics: ColorMetrics,
    operator_id: Optional[str] = None,
    gps: Optional[Dict[str, Any]] = None
) -> EvidenceRecord:
    """
    Builds the digital evidence record and persists the original image to disk.
    """
    test_id = generate_test_id()
    now_utc = datetime.now(timezone.utc).isoformat()
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Compute SHA-256 hash directly on raw captured bytes
    image_hash = compute_image_sha256(image_bytes)

    # Save original image to evidence directory
    image_filename = f"evidence_{test_id}.jpg"
    image_path = EVIDENCE_DIR / image_filename
    with open(image_path, "wb") as f:
        f.write(image_bytes)

    # Normalize GPS metadata
    gps_data = gps or {}
    if "latitude" not in gps_data or "longitude" not in gps_data:
        normalized_gps = {
            "status": "unavailable",
            "latitude": None,
            "longitude": None,
            "accuracy_meters": None,
            "note": "GPS coordinates not available at capture time."
        }
    else:
        normalized_gps = {
            "status": "available",
            "latitude": float(gps_data["latitude"]),
            "longitude": float(gps_data["longitude"]),
            "accuracy_meters": float(gps_data.get("accuracy_meters", 10.0)),
            "note": "Device GPS fix captured."
        }

    operator = (operator_id or "").strip() or "FIELD-OP-DEFAULT"

    record = EvidenceRecord(
        test_id=test_id,
        timestamp_utc=now_utc,
        timestamp_local=now_local,
        operator_id=operator,
        gps=normalized_gps,
        kit_profile={
            "profile_id": profile.profile_id,
            "name": profile.name,
            "version": profile.version,
            "is_simulated": profile.is_simulated
        },
        quality_report=quality.to_dict(),
        color_analysis=color_metrics.to_dict(),
        result=result,
        image_sha256=image_hash,
        image_filename=image_filename,
        disclaimer=STANDARD_DISCLAIMER
    )

    return record
