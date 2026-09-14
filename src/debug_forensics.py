"""
Forensic Debugging Module for PS26231 MVP Live Camera Capture.
Saves intermediate visual artifacts and logs detailed diagnostics for every stage:
1. Raw frame & metadata (debug_raw.jpg)
2. Quality metrics (blur, exposure, glare)
3. Card detection & contour overlay (debug_card_contour.jpg)
4. Perspective warp (debug_warped.jpg)
5. Canonical orientation (debug_orientation.jpg)
6. Sampling overlay with ROIs (debug_sampling_overlay.jpg)
7. Patch RGBs & Reaction circle detection
8. Illumination calibration
9. Classification decision rule
"""
import io
import json
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from PIL import Image, ExifTags

from src.config import DATA_DIR, MIN_LAPLACIAN_VARIANCE
from src.quality import check_blur, check_exposure, check_glare
from src.detection import order_quad_points, four_point_transform, extract_mean_color
from src.calibration import apply_color_calibration
from src.color import rgb_to_cielab, calculate_delta_e00
from src.engine import classify_result, get_kit_profile
from src.models import KitProfile

DEBUG_DIR = DATA_DIR / "debug"
DEBUG_DIR.mkdir(parents=True, exist_ok=True)


def run_forensic_debug(
    image_bytes: bytes,
    profile: Optional[KitProfile] = None,
    save_artifacts: bool = True
) -> Dict[str, Any]:
    """
    Executes forensic inspection on raw image bytes, saving all required debug images
    and returning a comprehensive numerical dictionary across all 9 stages.
    """
    if profile is None:
        profile = get_kit_profile("SIM-PROFILE-ALPHA")

    report: Dict[str, Any] = {}

    # 1. Raw browser-captured image
    if save_artifacts:
        (DEBUG_DIR / "debug_raw.jpg").write_bytes(image_bytes)

    nparr = np.frombuffer(image_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img_bgr is None:
        report["stage1_raw"] = {"error": "Failed to decode image bytes"}
        return report

    img_h, img_w = img_bgr.shape[:2]

    exif_info = {}
    img_format = "Unknown"
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        img_format = pil_img.format or "JPEG"
        raw_exif = pil_img.getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                exif_info[tag_name] = str(value)
    except Exception as e:
        exif_info["error"] = str(e)

    report["stage1_raw"] = {
        "width": img_w,
        "height": img_h,
        "resolution": f"{img_w}x{img_h}",
        "format": img_format,
        "byte_size": len(image_bytes),
        "exif_orientation": exif_info.get("Orientation", "None / Not Specified"),
        "exif_details": exif_info
    }

    # 2. Quality Assessment Stage
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    blur_passed, blur_score = check_blur(gray)
    exp_passed, exp_status, under_ratio, over_ratio = check_exposure(gray)
    glare_passed, glare_detected, glare_ratio = check_glare(img_bgr)

    quality_issues = []
    if not blur_passed:
        quality_issues.append(f"Blurry frame: Laplacian variance {blur_score:.1f} < {MIN_LAPLACIAN_VARIANCE}")
    if not exp_passed:
        quality_issues.append(f"Exposure failure: {exp_status} (under={under_ratio*100:.1f}%, over={over_ratio*100:.1f}%)")
    if not glare_passed:
        quality_issues.append(f"Specular glare hotspot: {glare_ratio*100:.1f}% area")

    report["stage2_quality"] = {
        "blur_score": round(blur_score, 1),
        "blur_threshold": MIN_LAPLACIAN_VARIANCE,
        "blur_passed": blur_passed,
        "exposure_status": exp_status,
        "exposure_passed": exp_passed,
        "underexposed_ratio": round(under_ratio, 4),
        "overexposed_ratio": round(over_ratio, 4),
        "glare_detected": glare_detected,
        "glare_ratio": round(glare_ratio, 4),
        "glare_passed": glare_passed,
        "overall_quality_passed": blur_passed and exp_passed and glare_passed,
        "rejection_reasons": quality_issues
    }

    # 3. Card Detection & Contour Overlay
    det_w = 800
    scale = det_w / float(img_w) if img_w > det_w else 1.0
    det_h = int(round(img_h * scale))
    det_img = cv2.resize(img_bgr, (det_w, det_h), interpolation=cv2.INTER_AREA) if scale != 1.0 else img_bgr

    det_gray = cv2.cvtColor(det_img, cv2.COLOR_BGR2GRAY)
    det_blurred = cv2.GaussianBlur(det_gray, (5, 5), 0)
    edges = cv2.Canny(det_blurred, 40, 150)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    edges = cv2.dilate(edges, kernel, iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    card_contour = None
    max_area = 0.0
    min_area = (det_w * det_h) * 0.05
    is_fallback = False

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > min_area:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.03 * peri, True)
            if len(approx) == 4:
                x, y, w, h = cv2.boundingRect(approx)
                aspect = max(w, h) / max(min(w, h), 1)
                if 1.1 <= aspect <= 2.5 and area > max_area:
                    card_contour = approx
                    max_area = area

    contour_overlay = img_bgr.copy()
    if card_contour is None:
        aspect = max(img_w, img_h) / max(min(img_w, img_h), 1)
        if 1.2 <= aspect <= 2.5:
            orig_pts = np.array([
                [0, 0],
                [img_w - 1, 0],
                [img_w - 1, img_h - 1],
                [0, img_h - 1]
            ], dtype=np.float32)
            is_fallback = True
            card_found = True
            cv2.putText(contour_overlay, "FALLBACK: WHOLE FRAME USED", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
        else:
            card_found = False
            orig_pts = None
            cv2.putText(contour_overlay, "CARD NOT DETECTED", (50, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
    else:
        card_found = True
        orig_pts = (card_contour.reshape(4, 2) / scale).astype("float32")
        pts_int = orig_pts.astype(np.int32).reshape((-1, 1, 2))
        cv2.polylines(contour_overlay, [pts_int], isClosed=True, color=(0, 255, 0), thickness=6)
        for i, pt in enumerate(orig_pts):
            cv2.circle(contour_overlay, (int(pt[0]), int(pt[1])), 10, (0, 0, 255), -1)
            cv2.putText(contour_overlay, f"P{i}", (int(pt[0]) + 15, int(pt[1]) + 15), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

    if save_artifacts:
        cv2.imwrite(str(DEBUG_DIR / "debug_card_contour.jpg"), contour_overlay)

    area_pct = (max_area / (det_w * det_h) * 100.0) if (card_found and not is_fallback) else (100.0 if is_fallback else 0.0)
    report["stage3_card_detection"] = {
        "card_detected": card_found,
        "is_fallback_full_frame": is_fallback,
        "detection_scale": round(scale, 4),
        "contour_area_pct": round(area_pct, 1),
        "quad_points": orig_pts.tolist() if orig_pts is not None else None
    }

    if not card_found or orig_pts is None:
        report["failure_stage"] = "stage3_card_detection"
        report["root_cause"] = "Reference card border was not detected in camera frame."
        return report

    # 4. Perspective Warp
    rect = order_quad_points(orig_pts)
    (tl, tr, br, bl) = rect
    quad_w = max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl))
    quad_h = max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl))

    canonical_w, canonical_h = 400, 240
    is_portrait_quad = quad_h > quad_w

    if is_portrait_quad:
        dst = np.array([
            [0, 0],
            [canonical_h - 1, 0],
            [canonical_h - 1, canonical_w - 1],
            [0, canonical_w - 1]
        ], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        warped_initial = cv2.warpPerspective(img_bgr, M, (canonical_h, canonical_w))
    else:
        dst = np.array([
            [0, 0],
            [canonical_w - 1, 0],
            [canonical_w - 1, canonical_h - 1],
            [0, canonical_h - 1]
        ], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        warped_initial = cv2.warpPerspective(img_bgr, M, (canonical_w, canonical_h))

    if save_artifacts:
        cv2.imwrite(str(DEBUG_DIR / "debug_warped.jpg"), warped_initial)

    report["stage4_warp"] = {
        "is_portrait_capture": is_portrait_quad,
        "quad_physical_width": round(float(quad_w), 1),
        "quad_physical_height": round(float(quad_h), 1),
        "initial_warped_shape": list(warped_initial.shape[:2]),
        "confirms_physical_card_not_frame": not is_fallback
    }

    # 5. Orientation Normalization
    if is_portrait_quad:
        c1 = cv2.rotate(warped_initial, cv2.ROTATE_90_CLOCKWISE)
        c2 = cv2.rotate(warped_initial, cv2.ROTATE_90_COUNTERCLOCKWISE)
        candidates = [
            ("rot_90_cw", c1),
            ("rot_90_ccw", c2),
            ("rot_270_cw", cv2.rotate(c1, cv2.ROTATE_180)),
            ("rot_270_ccw", cv2.rotate(c2, cv2.ROTATE_180))
        ]
    else:
        candidates = [
            ("none", warped_initial),
            ("rot_180", cv2.rotate(warped_initial, cv2.ROTATE_180))
        ]

    best_cand_name = candidates[0][0]
    best_card = candidates[0][1]
    best_blue_score = -1
    blue_scores = {}

    for name, cand in candidates:
        ch, cw = cand.shape[:2]
        bl_roi = cand[int(ch * 0.6):, :int(cw * 0.35)]
        hsv = cv2.cvtColor(bl_roi, cv2.COLOR_BGR2HSV)
        blue_cnt = int(np.count_nonzero((hsv[:, :, 0] >= 90) & (hsv[:, :, 0] <= 135) & (hsv[:, :, 1] >= 40)))
        blue_scores[name] = blue_cnt
        if blue_cnt > best_blue_score:
            best_blue_score = blue_cnt
            best_cand_name = name
            best_card = cand

    canonical_card = best_card

    if save_artifacts:
        cv2.imwrite(str(DEBUG_DIR / "debug_orientation.jpg"), canonical_card)

    report["stage5_orientation"] = {
        "chosen_rotation": best_cand_name,
        "blue_fiducial_scores": blue_scores,
        "canonical_shape": list(canonical_card.shape[:2])
    }

    # 6 & 7: Patch Sampling & Reaction Region with Visual Overlay
    cw, ch = canonical_w, canonical_h
    pw, ph = int(cw * 0.09), int(ch * 0.14)
    px = int(cw * 0.08)

    patches_y = {
        "white": int(ch * 0.14),
        "gray": int(ch * 0.34),
        "black": int(ch * 0.53),
        "blue": int(ch * 0.72)
    }

    patches_rgb = {}
    for name, py in patches_y.items():
        patches_rgb[name] = extract_mean_color(canonical_card, px, py, pw, ph)

    rx_start, rx_end = int(cw * 0.52), int(cw * 0.95)
    ry_start, ry_end = int(ch * 0.15), int(ch * 0.85)
    reac_roi = canonical_card[ry_start:ry_end, rx_start:rx_end]
    reac_gray = cv2.cvtColor(reac_roi, cv2.COLOR_BGR2GRAY)
    reac_blur = cv2.GaussianBlur(reac_gray, (9, 9), 2)
    circles = cv2.HoughCircles(
        reac_blur, cv2.HOUGH_GRADIENT, dp=1, minDist=30,
        param1=50, param2=25, minRadius=20, maxRadius=55
    )

    hough_detected = False
    if circles is not None:
        c = circles[0][0]
        full_cx = rx_start + int(c[0])
        full_cy = ry_start + int(c[1])
        circle_r = int(c[2])
        sample_r = max(10, int(circle_r * 0.5))
        hough_detected = True
    else:
        full_cx, full_cy, circle_r = int(cw * 0.75), int(ch * 0.48), 38
        sample_r = 20

    reaction_mask = np.zeros((ch, cw), dtype=np.uint8)
    cv2.circle(reaction_mask, (full_cx, full_cy), sample_r, 255, -1)
    reac_bgr = cv2.mean(canonical_card, mask=reaction_mask)[:3]
    reaction_rgb = (float(reac_bgr[2]), float(reac_bgr[1]), float(reac_bgr[0]))

    # Draw Sampling Overlay
    sampling_overlay = canonical_card.copy()
    for name, py in patches_y.items():
        cv2.rectangle(sampling_overlay, (px, py), (px + pw, py + ph), (0, 255, 0), 2)
        cv2.putText(sampling_overlay, name.upper()[:3], (px + pw + 4, py + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 0), 1)

    cv2.circle(sampling_overlay, (full_cx, full_cy), circle_r, (0, 255, 255), 1)
    cv2.circle(sampling_overlay, (full_cx, full_cy), sample_r, (0, 0, 255), 2)
    cv2.putText(sampling_overlay, "REACTION", (full_cx - 25, full_cy - circle_r - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

    if save_artifacts:
        cv2.imwrite(str(DEBUG_DIR / "debug_sampling_overlay.jpg"), sampling_overlay)

    report["stage6_patches"] = {
        "white_rgb": [round(c, 1) for c in patches_rgb["white"]],
        "gray_rgb": [round(c, 1) for c in patches_rgb["gray"]],
        "black_rgb": [round(c, 1) for c in patches_rgb["black"]],
        "blue_rgb": [round(c, 1) for c in patches_rgb["blue"]],
        "sampling_boxes": {k: [px, py, pw, ph] for k, py in patches_y.items()}
    }

    report["stage7_reaction"] = {
        "hough_circle_detected": hough_detected,
        "circle_center": [full_cx, full_cy],
        "outer_radius": circle_r,
        "sample_inner_radius": sample_r,
        "reaction_rgb": [round(c, 1) for c in reaction_rgb]
    }

    # 8. Calibration
    calibrated_rgb, cal_result = apply_color_calibration(
        observed_reaction_rgb=reaction_rgb,
        observed_white_rgb=patches_rgb["white"]
    )
    calibrated_lab = rgb_to_cielab(calibrated_rgb)

    report["stage8_calibration"] = {
        "calibration_gains": cal_result.gains,
        "calibrated_rgb": list(calibrated_rgb),
        "calibrated_lab": [round(x, 2) for x in calibrated_lab]
    }

    # 9. Classification
    dE_pos = calculate_delta_e00(calibrated_lab, profile.positive_target.target_lab)
    dE_neg = calculate_delta_e00(calibrated_lab, profile.negative_target.target_lab)
    margin = dE_neg - dE_pos

    is_positive = (dE_pos <= profile.positive_target.max_delta_e) and (margin >= profile.ambiguity_margin)
    is_negative = (dE_neg <= profile.negative_target.max_delta_e) and (dE_pos - dE_neg >= profile.ambiguity_margin)

    if dE_pos > profile.max_acceptable_delta_e and dE_neg > profile.max_acceptable_delta_e:
        final_result = "Inconclusive"
        rule = f"Outside all profile boundaries (dE_pos={dE_pos:.1f}, dE_neg={dE_neg:.1f} > {profile.max_acceptable_delta_e})"
    elif abs(dE_pos - dE_neg) < profile.ambiguity_margin and (dE_pos <= profile.positive_target.max_delta_e or dE_neg <= profile.negative_target.max_delta_e):
        final_result = "Inconclusive"
        rule = f"Ambiguous boundary: separation |dE_pos - dE_neg| ({abs(dE_pos - dE_neg):.1f}) < margin ({profile.ambiguity_margin})"
    elif is_positive:
        final_result = "Positive"
        rule = f"Matched positive proxy target (dE={dE_pos:.1f} <= {profile.positive_target.max_delta_e}, margin={margin:.1f} >= {profile.ambiguity_margin})"
    elif is_negative:
        final_result = "Negative"
        rule = f"Matched negative proxy target (dE={dE_neg:.1f} <= {profile.negative_target.max_delta_e}, margin={dE_pos - dE_neg:.1f} >= {profile.ambiguity_margin})"
    else:
        final_result = "Inconclusive"
        rule = f"Does not meet decisive criteria (dE_pos={dE_pos:.1f}, dE_neg={dE_neg:.1f})"

    report["stage9_classification"] = {
        "target_positive_lab": profile.positive_target.target_lab,
        "target_negative_lab": profile.negative_target.target_lab,
        "delta_e_positive": round(dE_pos, 2),
        "delta_e_negative": round(dE_neg, 2),
        "margin": round(margin, 2),
        "max_delta_e_positive": profile.positive_target.max_delta_e,
        "max_delta_e_negative": profile.negative_target.max_delta_e,
        "final_result": final_result,
        "decision_rule": rule
    }

    if save_artifacts:
        def _json_default(obj):
            if isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            if isinstance(obj, (np.integer, int)):
                return int(obj)
            if isinstance(obj, (np.floating, float)):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            return str(obj)

        (DEBUG_DIR / "debug_report.json").write_text(json.dumps(report, indent=2, default=_json_default))

    return report
