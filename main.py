"""
PS26231 — Digital Companion for Field Drug Testing MVP
Main Application Entry Point.
Launches the field companion web UI or runs an automated end-to-end CLI demonstration.
"""
import sys
import os
import argparse
from pathlib import Path
from src.config import DEMO_SAMPLES_DIR, STANDARD_DISCLAIMER
from src.engine import list_available_profiles, get_kit_profile
from src.pipeline import run_pipeline
from src.demo_data import generate_all_demo_samples
from src.history import init_database, search_records


def run_cli_demo():
    """
    Executes a terminal-based demonstration across simulated proxy cases.
    """
    print("=" * 70)
    print("PS26231 -- Digital Companion for Field Drug Testing MVP")
    print("Architecture: Quality Check -> Card Detection -> Calibration ->")
    print("              CIELAB -> Delta E -> Profile Rules -> SHA-256 Record")
    print("=" * 70)
    print(f"NOTICE: {STANDARD_DISCLAIMER}\n")

    # Ensure demo samples exist
    generate_all_demo_samples()
    init_database()

    profiles = list_available_profiles()
    print(f"Loaded {len(profiles)} Configured Simulated Kit Profiles:")
    for p in profiles:
        print(f"  [{p.profile_id}] {p.name} (Reaction Timing: {p.timing_seconds}s)")
    print()

    profile_alpha = get_kit_profile("SIM-PROFILE-ALPHA")

    demo_cases = [
        ("sample_alpha_positive.jpg", "SIM-PROFILE-ALPHA", "Testing Alpha Positive Proxy (Purple)"),
        ("sample_alpha_negative.jpg", "SIM-PROFILE-ALPHA", "Testing Alpha Negative Proxy (Amber)"),
        ("sample_alpha_inconclusive.jpg", "SIM-PROFILE-ALPHA", "Testing Alpha Inconclusive Proxy (Ambiguous)"),
        ("sample_beta_positive.jpg", "SIM-PROFILE-BETA", "Testing Beta Positive Proxy (Blue)"),
        ("sample_blurry_rejection.jpg", "SIM-PROFILE-ALPHA", "Testing Quality Rejection (Blurry Frame)")
    ]

    for filename, prof_id, desc in demo_cases:
        print("-" * 70)
        print(f"CASE: {desc}")
        sample_path = DEMO_SAMPLES_DIR / filename
        prof = get_kit_profile(prof_id)

        with open(sample_path, "rb") as f:
            img_bytes = f.read()

        res = run_pipeline(
            image_bytes=img_bytes,
            profile=prof,
            operator_id="CLI-DEMO-OFFICER",
            gps_data={"latitude": 28.6139, "longitude": 77.2090, "accuracy_meters": 5.0},
            persist=True
        )

        q = res.quality_report
        print(f"  [Quality Check] Passed: {q.passed} | Blur Score: {q.blur_score} | Exposure: {q.exposure_status} | Glare: {not q.glare_passed}")
        if not q.passed:
            print(f"  >> REJECTED: {'; '.join(q.issues)}")
            continue

        ev = res.evidence_record
        ca = ev.color_analysis
        print(f"  [Colour Science] Calibrated RGB: {ca['calibrated_rgb']} -> CIELAB: {ca['calibrated_lab']}")
        print(f"  [Delta E Analysis] dE(Pos): {ca['delta_e_positive']} | dE(Neg): {ca['delta_e_negative']}")
        print(f"  [Result Outcome] Presumptive {ev.result.upper()} ({res.reasoning})")
        print(f"  [Evidence Record] Test ID: {ev.test_id}")
        print(f"  [Integrity] SHA-256: {ev.image_sha256[:20]}...{ev.image_sha256[-8:]} (Verified)")

    print("\n" + "=" * 70)
    records = search_records(limit=10)
    print(f"Searchable SQLite History: Currently holds {len(records)} test records.")
    print("=" * 70)


def get_lan_ip():
    """Returns local LAN IPv4 address."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start_server(port=5000, host="0.0.0.0"):
    """
    Launches the Flask web server listening on all network interfaces (0.0.0.0).
    Supports Localhost, LAN HTTP, Tailscale HTTPS, and Cloudflare Quick Tunnel.
    """
    from src.web.app import app
    lan_ip = get_lan_ip()
    print("=" * 70)
    print("Starting PS26231 Field Companion Web UI (Single Source of Truth)...")
    print(f"  1. Localhost (Dev/Test):      http://localhost:{port}")
    print(f"  2. LAN Wi-Fi (Same Network):   http://{lan_ip}:{port}")
    print("  3. Tailscale HTTPS (Private):  https://<tailscale-hostname>")
    print(f"  4. Cloudflare Tunnel (Shared): cloudflared tunnel --url http://localhost:{port}")
    print("=" * 70)
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    default_port = int(os.environ.get("PORT", 5000))
    parser = argparse.ArgumentParser(description="PS26231 Digital Companion for Field Drug Testing")
    parser.add_argument("--cli", action="store_true", help="Run command-line demonstration across sample cases")
    parser.add_argument("--port", type=int, default=default_port, help=f"Web server port (default: {default_port})")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Web server host (default: 0.0.0.0)")

    args = parser.parse_args()

    if args.cli:
        run_cli_demo()
    else:
        start_server(port=args.port, host=args.host)