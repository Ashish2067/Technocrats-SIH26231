"""
MVP-Simple Colour Calibration module for PS26231.
Performs linear channel scaling (white-point gain adjustment) based on the
observed prototype reference card white patch.

Kept intentionally simple per MVP requirements:
Reference card -> linear gain calibration -> CIELAB -> Delta E.
"""
import numpy as np
from typing import Tuple, List
from src.config import PROTOTYPE_CARD_NOMINAL
from src.models import CalibrationResult


def compute_calibration_gains(
    observed_white_rgb: Tuple[float, float, float],
    nominal_white_rgb: Tuple[float, float, float] = PROTOTYPE_CARD_NOMINAL["white"]
) -> Tuple[float, float, float]:
    """
    Computes per-channel gain multipliers:
    k_c = nominal_white_c / max(observed_white_c, 1.0)
    Gains are clamped between [0.3, 3.0] to prevent extreme distortion.
    """
    gains = []
    for obs, nom in zip(observed_white_rgb, nominal_white_rgb):
        obs_safe = max(float(obs), 1.0)
        gain = nom / obs_safe
        # Clamp to realistic lighting range
        gain_clamped = max(0.3, min(3.0, gain))
        gains.append(gain_clamped)

    return (float(gains[0]), float(gains[1]), float(gains[2]))


def apply_color_calibration(
    observed_reaction_rgb: Tuple[float, float, float],
    observed_white_rgb: Tuple[float, float, float]
) -> Tuple[Tuple[int, int, int], CalibrationResult]:
    """
    Calibrates the reaction zone RGB using the detected white patch gains.
    Returns (calibrated_rgb, calibration_result).
    """
    k_r, k_g, k_b = compute_calibration_gains(observed_white_rgb)

    r_cal = int(np.clip(round(observed_reaction_rgb[0] * k_r), 0, 255))
    g_cal = int(np.clip(round(observed_reaction_rgb[1] * k_g), 0, 255))
    b_cal = int(np.clip(round(observed_reaction_rgb[2] * k_b), 0, 255))

    calibrated_rgb = (r_cal, g_cal, b_cal)

    result = CalibrationResult(
        observed_white_rgb=[round(x, 1) for x in observed_white_rgb],
        gains=[round(k_r, 4), round(k_g, 4), round(k_b, 4)],
        success=True,
        message=f"Illumination normalized: R x{k_r:.3f}, G x{k_g:.3f}, B x{k_b:.3f}"
    )

    return calibrated_rgb, result
