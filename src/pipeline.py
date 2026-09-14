"""
Unified Analysis Pipeline Coordinator for PS26231 MVP.
Orchestrates the fixed 12-step architecture:
Image Capture -> Quality Check -> Card Detection -> Colour Calibration ->
CIELAB -> Delta E -> Profile Evaluation -> Result Engine -> Evidence Record -> History DB.
"""
import cv2
import numpy as np
from typing import Dict, Any, Optional, Tuple
from src.models import KitProfile, QualityReport, ColorMetrics, EvidenceRecord
from src.quality import assess_image_quality
from src.detection import detect_prototype_card, DetectedCard
from src.calibration import apply_color_calibration
from src.color import compute_color_metrics
from src.engine import classify_result, get_kit_profile
from src.evidence import create_evidence_record
from src.history import save_record
from src.debug_forensics import run_forensic_debug


class PipelineExecutionResult:
    def __init__(
        self,
        success: bool,
        quality_report: QualityReport,
        card_detected: bool,
        evidence_record: Optional[EvidenceRecord] = None,
        reasoning: str = "",
        annotated_image_bgr: Optional[np.ndarray] = None
    ):
        self.success = success
        self.quality_report = quality_report
        self.card_detected = card_detected
        self.evidence_record = evidence_record
        self.reasoning = reasoning
        self.annotated_image_bgr = annotated_image_bgr

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "quality_report": self.quality_report.to_dict(),
            "card_detected": self.card_detected,
            "evidence_record": self.evidence_record.to_dict() if self.evidence_record else None,
            "reasoning": self.reasoning
        }


def run_pipeline(
    image_bytes: bytes,
    profile: KitProfile,
    operator_id: Optional[str] = None,
    gps_data: Optional[Dict[str, Any]] = None,
    persist: bool = True
) -> PipelineExecutionResult:
    """
    Executes the end-to-end PS26231 MVP pipeline.
    """
    # 0. Always execute forensic logging and save required debug artifacts
    try:
        run_forensic_debug(image_bytes, profile=profile, save_artifacts=True)
    except Exception as e:
        print(f"Forensic debug logging warning: {e}")

    # 1. Decode image bytes
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        quality = QualityReport(
            passed=False, blur_score=0.0, blur_passed=False,
            exposure_status="invalid", exposure_passed=False,
            glare_detected=False, glare_passed=False, card_visible=False,
            issues=["Failed to decode image. Unsupported or corrupted format."]
        )
        return PipelineExecutionResult(
            success=False,
            quality_report=quality,
            card_detected=False,
            reasoning="Image decoding failed."
        )

    # 2. Reference Card Detection
    card: DetectedCard = detect_prototype_card(img_bgr)

    # 3. Image Quality Assessment
    quality = assess_image_quality(
        img_bgr,
        card_detected=card.found,
        reaction_mask=card.reaction_mask if card.found else None,
        warped_card=card.warped_card if card.found else None
    )

    # Gate: If quality checks failed, reject with recapture advice
    if not quality.passed:
        return PipelineExecutionResult(
            success=False,
            quality_report=quality,
            card_detected=card.found,
            reasoning=f"Image rejected due to quality check failures: {'; '.join(quality.issues)}"
        )

    # 4. Colour Calibration (Linear patch scaling based on White patch)
    white_rgb = card.patches_rgb.get("white", (240.0, 240.0, 240.0))
    raw_reaction_rgb = card.reaction_rgb if card.reaction_rgb is not None else (128, 128, 128)

    calibrated_rgb, cal_result = apply_color_calibration(
        observed_reaction_rgb=raw_reaction_rgb,
        observed_white_rgb=white_rgb
    )

    # 5. CIELAB conversion & CIEDE2000 Delta E computation
    color_metrics = compute_color_metrics(
        raw_rgb=(int(raw_reaction_rgb[0]), int(raw_reaction_rgb[1]), int(raw_reaction_rgb[2])),
        calibrated_rgb=calibrated_rgb,
        target_pos_lab=profile.positive_target.target_lab,
        target_neg_lab=profile.negative_target.target_lab
    )

    # 6. Classification Engine (Positive / Negative / Inconclusive)
    outcome, reasoning = classify_result(color_metrics, profile)

    # 7. Digital Evidence Record Generation
    record = create_evidence_record(
        image_bytes=image_bytes,
        result=outcome,
        profile=profile,
        quality=quality,
        color_metrics=color_metrics,
        operator_id=operator_id,
        gps=gps_data
    )

    # 8. Persist to Searchable History Database
    if persist:
        save_record(record)

    return PipelineExecutionResult(
        success=True,
        quality_report=quality,
        card_detected=True,
        evidence_record=record,
        reasoning=reasoning
    )
