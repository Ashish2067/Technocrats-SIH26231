"""
Image Quality Assessment module for PS26231 MVP.
Evaluates blur, exposure, glare/specular highlights, and reference card visibility.
Rejects or requests recapture if an image is unsuitable for colorimetry.
"""
import cv2
import numpy as np
from typing import Tuple, List, Optional
from src.config import (
    MIN_LAPLACIAN_VARIANCE,
    STANDARD_BLUR_WIDTH,
    MAX_UNDEREXPOSED_RATIO,
    MAX_OVEREXPOSED_RATIO,
    MAX_GLARE_RATIO,
)
from src.models import QualityReport


def check_blur(
    img_gray: np.ndarray,
    threshold: float = MIN_LAPLACIAN_VARIANCE,
    target_width: int = STANDARD_BLUR_WIDTH
) -> Tuple[bool, float]:
    """
    Computes blur score using variance of the Laplacian operator on a standardized resolution.
    Higher score indicates sharper focus.
    Standardizing resolution ensures deterministic evaluation independent of camera sensor megapixels.
    """
    if img_gray is None or img_gray.size == 0:
        return False, 0.0

    h, w = img_gray.shape[:2]
    if w > 0 and h > 0 and w != target_width:
        scale = target_width / float(w)
        target_h = max(1, int(round(h * scale)))
        eval_gray = cv2.resize(img_gray, (target_width, target_h), interpolation=cv2.INTER_AREA)
    else:
        eval_gray = img_gray

    score = float(cv2.Laplacian(eval_gray, cv2.CV_64F).var())
    passed = score >= threshold
    return passed, score


def check_exposure(
    img_gray: np.ndarray,
    under_ratio_max: float = MAX_UNDEREXPOSED_RATIO,
    over_ratio_max: float = MAX_OVEREXPOSED_RATIO
) -> Tuple[bool, str, float, float]:
    """
    Evaluates histogram distribution to flag underexposure (too dark)
    or overexposure (clipping/washed out).
    """
    total_pixels = img_gray.size
    if total_pixels == 0:
        return False, "empty", 0.0, 0.0

    under_ratio = float(np.count_nonzero(img_gray < 20) / total_pixels)
    over_ratio = float(np.count_nonzero(img_gray > 245) / total_pixels)

    if under_ratio > under_ratio_max:
        return False, "underexposed", under_ratio, over_ratio
    elif over_ratio > over_ratio_max:
        return False, "overexposed", under_ratio, over_ratio
    else:
        return True, "normal", under_ratio, over_ratio


def check_glare(
    img_bgr: np.ndarray,
    roi_mask: Optional[np.ndarray] = None,
    glare_ratio_max: float = MAX_GLARE_RATIO
) -> Tuple[bool, bool, float]:
    """
    Detects specular reflection / glare hotspot.
    Glare typically manifests as clusters of high luminance with near-zero saturation.
    """
    if img_bgr is None or img_bgr.size == 0:
        return True, False, 0.0

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    # Glare condition: very high brightness (V > 248) and very low saturation (S < 30)
    glare_mask = (val >= 248) & (sat <= 30)

    if roi_mask is not None:
        if roi_mask.shape[:2] != img_bgr.shape[:2]:
            roi_mask = cv2.resize(roi_mask, (img_bgr.shape[1], img_bgr.shape[0]), interpolation=cv2.INTER_NEAREST)

        target_pixels = np.count_nonzero(roi_mask)
        if target_pixels == 0:
            return True, False, 0.0
        glare_pixels = np.count_nonzero(glare_mask & (roi_mask > 0))
        glare_ratio = float(glare_pixels / target_pixels)
    else:
        glare_ratio = float(np.count_nonzero(glare_mask) / (img_bgr.shape[0] * img_bgr.shape[1]))

    glare_detected = glare_ratio > glare_ratio_max
    glare_passed = not glare_detected
    return glare_passed, glare_detected, glare_ratio


def assess_image_quality(
    img_bgr: np.ndarray,
    card_detected: bool = True,
    reaction_mask: Optional[np.ndarray] = None,
    warped_card: Optional[np.ndarray] = None
) -> QualityReport:
    """
    Runs full suite of image quality checks.
    Produces structured QualityReport with specific issues for recapture guidance.
    """
    if img_bgr is None or img_bgr.size == 0:
        return QualityReport(
            passed=False,
            blur_score=0.0,
            blur_passed=False,
            exposure_status="invalid",
            exposure_passed=False,
            glare_detected=False,
            glare_passed=False,
            card_visible=False,
            issues=["Unable to decode image data."]
        )

    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    issues: List[str] = []

    # 1. Blur Check (evaluated on whole captured frame)
    blur_passed, blur_score = check_blur(gray)
    if not blur_passed:
        issues.append(
            f"Image is blurry (Laplacian variance {blur_score:.1f} < {MIN_LAPLACIAN_VARIANCE}). "
            "Hold the device steady and refocus."
        )

    # 2. Exposure Check (evaluated on whole captured frame)
    exposure_passed, exposure_status, under_ratio, over_ratio = check_exposure(gray)
    if not exposure_passed:
        if exposure_status == "underexposed":
            issues.append(
                f"Image is underexposed ({under_ratio * 100:.1f}% dark pixels). "
                "Increase ambient illumination."
            )
        elif exposure_status == "overexposed":
            issues.append(
                f"Image is overexposed ({over_ratio * 100:.1f}% clipped bright pixels). "
                "Reduce direct glare or harsh lighting."
            )

    # 3. Glare Check (evaluated on reaction ROI or frame)
    glare_target_img = warped_card if (warped_card is not None and reaction_mask is not None) else img_bgr
    glare_passed, glare_detected, glare_ratio = check_glare(glare_target_img, roi_mask=reaction_mask)
    if not glare_passed:
        issues.append(
            f"Excessive specular glare detected ({glare_ratio * 100:.1f}% hotspot area). "
            "Angle camera slightly away from direct reflection."
        )

    # 4. Card Visibility Check
    if not card_detected:
        issues.append(
            "Reference colour card was not detected in the frame. "
            "Ensure the card is clearly visible, upright, and unoccluded."
        )

    all_passed = blur_passed and exposure_passed and glare_passed and card_detected

    return QualityReport(
        passed=all_passed,
        blur_score=round(blur_score, 1),
        blur_passed=blur_passed,
        exposure_status=exposure_status,
        exposure_passed=exposure_passed,
        glare_detected=glare_detected,
        glare_passed=glare_passed,
        card_visible=card_detected,
        issues=issues
    )
