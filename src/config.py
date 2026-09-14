"""
Configuration constants and paths for PS26231 MVP.
"""
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
EVIDENCE_DIR = DATA_DIR / "evidence"
DEMO_SAMPLES_DIR = DATA_DIR / "demo_samples"
DATABASE_PATH = DATA_DIR / "evidence.db"

# Ensure runtime directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
PROFILES_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
DEMO_SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

# Image Quality Check Thresholds
MIN_LAPLACIAN_VARIANCE = 50.0       # Below this threshold indicates blur (at standard 640px width)
STANDARD_BLUR_WIDTH = 640          # Standardized evaluation width for deterministic blur scoring
MAX_UNDEREXPOSED_RATIO = 0.45      # >45% dark pixels (<20) indicates underexposure
MAX_OVEREXPOSED_RATIO = 0.25       # >25% clipped pixels (>245) indicates overexposure
MAX_GLARE_RATIO = 0.08             # >8% specular hotspot in reaction zone indicates glare

# Prototype Reference Card Specification (Nominal Values)
# NOTE: This is a minimal prototype reference card for safe proxy demonstration.
# These values are explicitly SIMULATED and NOT a field-kit standard.
PROTOTYPE_CARD_NOMINAL = {
    "white": (240, 240, 240),
    "gray": (128, 128, 128),
    "black": (25, 25, 25),
    "reference_blue": (40, 80, 200)
}

# Standard Disclaimer
STANDARD_DISCLAIMER = (
    "PRESUMPTIVE FIELD-TEST RESULT ONLY. "
    "Does not replace laboratory confirmatory testing. "
    "This system uses simulated kit profiles and safe proxy reactions for demonstration purposes."
)
