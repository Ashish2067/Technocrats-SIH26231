"""
Configurable Multi-Kit Interpretation Engine for PS26231 MVP.
Decoupled interpretation engine supporting multiple simulated kit profiles.
Evaluates calibrated CIELAB colours and Delta E distances to produce
Positive, Negative, or Inconclusive classifications.
"""
import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from src.config import PROFILES_DIR
from src.models import KitProfile, ColorMetrics


def load_profile_from_file(filepath: Path) -> KitProfile:
    """
    Loads a KitProfile from a JSON configuration file.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return KitProfile.from_dict(data)


def list_available_profiles() -> List[KitProfile]:
    """
    Scans the profiles directory and returns all configured kit profiles.
    """
    profiles = []
    for p in sorted(PROFILES_DIR.glob("*.json")):
        try:
            profile = load_profile_from_file(p)
            profiles.append(profile)
        except Exception as e:
            print(f"Warning: Failed to load profile {p}: {e}")
    return profiles


def get_kit_profile(profile_id: str) -> Optional[KitProfile]:
    """
    Retrieves a specific kit profile by ID.
    """
    for profile in list_available_profiles():
        if profile.profile_id.lower() == profile_id.lower():
            return profile
    return None


def classify_result(
    metrics: ColorMetrics,
    profile: KitProfile
) -> Tuple[str, str]:
    """
    Deterministic rule engine evaluating Delta E distances against kit profile targets.
    Returns (outcome, reasoning):
      outcome: 'Positive' | 'Negative' | 'Inconclusive'
      reasoning: Human-readable technical rationale explaining the classification.

    Inconclusive is treated as a first-class result:
    - If color is equidistant or within the ambiguity margin between targets.
    - If color is outside both target tolerances.
    - If overall distance exceeds max acceptable threshold.
    """
    dE_pos = metrics.delta_e_positive
    dE_neg = metrics.delta_e_negative
    max_pos = profile.positive_target.max_delta_e
    max_neg = profile.negative_target.max_delta_e
    margin = profile.ambiguity_margin
    max_acceptable = profile.max_acceptable_delta_e

    # Condition 1: Exceeds all acceptable reaction limits
    if dE_pos > max_acceptable and dE_neg > max_acceptable:
        return (
            "Inconclusive",
            f"Reaction colour is outside all expected profile boundaries (dE_pos={dE_pos:.1f}, dE_neg={dE_neg:.1f} > {max_acceptable:.1f})."
        )

    # Condition 2: Ambiguous boundary between positive and negative
    diff = abs(dE_pos - dE_neg)
    if diff < margin and (dE_pos <= max_pos or dE_neg <= max_neg):
        return (
            "Inconclusive",
            f"Ambiguous reaction: separation between positive and negative targets ({diff:.1f}) is within ambiguity margin ({margin:.1f})."
        )

    # Condition 3: Positive classification
    if dE_pos <= max_pos and (dE_neg - dE_pos) >= margin:
        return (
            "Positive",
            f"Calibrated colour matches positive proxy target (dE={dE_pos:.1f} <= {max_pos:.1f}, margin={dE_neg - dE_pos:.1f})."
        )

    # Condition 4: Negative classification
    if dE_neg <= max_neg and (dE_pos - dE_neg) >= margin:
        return (
            "Negative",
            f"Calibrated colour matches negative proxy target (dE={dE_neg:.1f} <= {max_neg:.1f}, margin={dE_pos - dE_neg:.1f})."
        )

    # Fallthrough: does not definitively satisfy positive or negative rules
    return (
        "Inconclusive",
        f"Reaction does not meet decisive criteria for positive or negative rules (dE_pos={dE_pos:.1f}, dE_neg={dE_neg:.1f})."
    )
