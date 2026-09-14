# PS26231 — Digital Companion for Field Drug Testing

> **Official Disclaimer:**  
> **PRESUMPTIVE FIELD-TEST RESULT ONLY.** This software does not replace laboratory confirmatory testing. All kit profiles, thresholds, and target color values in this repository are **SIMULATED / PROXY** values for safe demonstration and software validation. This application does NOT contain real narcotic test thresholds or Parichayan proprietary reagent data.

---

## 1. System Architecture

The MVP implements a deterministic, multi-kit digital companion for field colorimetric test kits without requiring proprietary hardware:

```
Existing Field-Test Kit
         ↓
Smartphone Camera Capture / Upload
         ↓
Image Quality Check
 ├── Blur (Laplacian variance >= 75)
 ├── Exposure (Histogram clipping bounds)
 ├── Specular Glare (Saturation/value hotspot check)
 └── Reference-card visibility
         ↓
Reference Card Detection & Perspective Normalization
         ↓
Colour Calibration (White-patch illuminant gain scaling)
         ↓
RGB → CIELAB Conversion (Standard D65 Illuminant)
         ↓
Colour / CIEDE2000 ΔE Analysis
         ↓
Selected Kit Profile (Configurable SIMULATED / PROXY rules)
         ↓
Result Engine
 ├── Positive
 ├── Negative
 └── Inconclusive (First-class result for ambiguous or boundary reactions)
         ↓
Digital Evidence Record
 ├── Original Image
 ├── Result & Technical Telemetry
 ├── Timestamp (UTC ISO 8601 & Local)
 ├── GPS Location (where available)
 ├── Operator Identifier
 ├── Kit Profile & Version
 └── SHA-256 Image Integrity Hash
         ↓
Searchable Test History (Persistent SQLite Database)
```

---

## 2. Key Features

- **Decoupled Multi-Kit Framework**: One reusable interpretation engine supporting dynamically loaded kit profiles (`data/profiles/*.json`). Demonstrates distinct proxy assays (`SIM-PROFILE-ALPHA` Purple Proxy and `SIM-PROFILE-BETA` Cobalt Blue Proxy).
- **Automated Image Quality Assessment**: Rejects unsuitable images with clear, actionable recapture guidance (blurry, underexposed, overexposed, or excessive glare).
- **Prototype Reference Colour Card**: Minimal 4-patch calibration target (White, 50% Gray, Black, Reference Blue) used in-frame to normalize camera white balance and ambient lighting variations. Printable card served directly at `/reference-card`.
- **Strictly Deterministic Colour Science**: Uses linear patch calibration and CIEDE2000 \(\Delta E_{00}\) metrics via `scikit-image`. **Zero machine learning or black-box inference**.
- **Inconclusive is a Real Result**: Non-binary classification where out-of-bounds or ambiguous reactions within the margin are explicitly classified as **Inconclusive**.
- **Tamper-Evident Digital Evidence**: Every test generates a structured evidence record with a SHA-256 cryptographic hash computed directly over the raw captured image bytes.
- **Searchable Test History**: Local SQLite repository with search and filter capabilities (by Test ID, Operator ID, Kit Profile, and Outcome).
- **Responsive Mobile Web Companion**: Flask-powered interface with live WebRTC camera capture, geolocation acquisition, 1-click demonstration samples, and modal evidence inspection.

---

## 3. Quick Start & Access Methods

The PS26231 MVP is designed around a **single source of truth**: one Flask server (`0.0.0.0:5000`) executes the deterministic CV pipeline and persists records to SQLite. It supports multiple optional access methods for different development and demonstration contexts without separate deployments or code branches.

### Prerequisites
Python 3.10+ with standard dependencies:
```bash
pip install -r requirements.txt
```

### Starting the Server
```bash
python main.py
```
The server listens on `0.0.0.0:5000`, making it immediately accessible via Localhost, LAN, or external HTTPS proxies.

---

### Access Methods & Security Contexts

Modern mobile browsers enforce a strict security model: WebRTC camera streaming (`getUserMedia`) and HTML5 Geolocation are only exposed in **secure contexts** (`https://` or `http://localhost`). The application handles these contexts gracefully without breaking workflow:

| Access Method | URL Format | Camera (Live Stream) | Camera (Upload / Native) | Geolocation | Best Used For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A. Localhost** | `http://localhost:5000` | Full WebRTC | Supported | Full Fix | Desktop development & test suite runs |
| **B. LAN HTTP** | `http://<lan-ip>:5000` | Blocked by browser | Supported (native camera) | Blocked (marked unavailable) | Quick device testing on same Wi-Fi |
| **C. Tailscale HTTPS** | `https://<host>.ts.net` | Full WebRTC | Supported | Full Fix | Encrypted private demonstrations |
| **D. Cloudflare Tunnel** | `https://<random>.trycloudflare.com` | Full WebRTC | Supported | Full Fix | Zero-setup sharing with teammates |

#### A. Local Development (Localhost)
- **URL**: `http://localhost:5000`
- **Execution**: `python main.py`
- **Browser Context**: Secure origin. Live camera and GPS work directly on the host machine.

#### B. Local Network Access (LAN HTTP)
- **URL**: `http://<lan-ip>:5000` (e.g. `http://10.222.199.222:5000`)
- **Finding IP**: Run `ipconfig` (Windows) or check the IP printed in the console at startup.
- **Browser Context**: Non-secure origin. Mobile browsers (Chrome/Safari) restrict WebRTC live streaming and Geolocation APIs on plain LAN HTTP.
- **Workflow Handling**: The application functions normally. Tapping the **Upload Photo** dropzone invokes the smartphone's native camera app or photo gallery via `<input type="file" accept="image/*">`, allowing photo capture and analysis. GPS is recorded as unavailable without breaking the evidence pipeline.

#### C. Tailscale HTTPS (Private Controlled Demos)
- **URL**: `https://<tailscale-hostname>` (e.g. `https://laptop-mrefhvq2.tailebe799.ts.net`)
- **Setup**: Configured via Tailscale Serve proxying to local port 5000:
  ```bash
  tailscale serve --bg 5000
  ```
- **Browser Context**: Secure origin (`https://`). Full WebRTC camera streaming and geolocation are available on authorized devices connected to the tailnet. Tailscale Funnel is NOT used (no public internet exposure).

#### D. Cloudflare Quick Tunnel (Temporary Zero-Setup HTTPS)
- **Use Case**: Quick demonstration to teammates, evaluators, or external phones without requiring Tailscale installation or account credentials.
- **Workflow**:
  - **Terminal 1** (Start Application):
    ```bash
    python main.py
    ```
  - **Terminal 2** (Start Temporary Tunnel):
    ```bash
    cloudflared tunnel --url http://localhost:5000
    ```
  - Share the temporary HTTPS URL printed in the terminal (e.g., `https://<random>.trycloudflare.com`).
- **Browser Context**: Secure origin (`https://`). Camera and GPS permissions work identically to standard HTTPS. No Cloudflare account or credentials required.

---

### Command-Line Demonstration
For automated verification without the web interface:
```bash
python main.py --cli
```
Executes an automated end-to-end walkthrough demonstrating:
1. Positive outcome on Profile Alpha (Purple proxy).
2. Negative outcome on Profile Alpha (Pale Amber proxy).
3. Inconclusive outcome on Profile Alpha (Ambiguous reaction).
4. Positive outcome on Profile Beta (Cobalt Blue proxy).
5. Automated quality rejection on a blurry capture.
6. Record persistence and SQLite history verification.

---

## 4. Running the Test Suite

Execute the complete 40-test unit and integration suite:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

The 40 tests validate all core modules across 7 test suites:
- Image quality checks (`tests/test_quality.py`)
- Patch calibration, RGB->CIELAB, CIEDE2000 \(\Delta E\) (`tests/test_color_and_calibration.py`)
- Multi-kit profile loading and classification rules (`tests/test_engine.py`)
- Evidence record assembly, SHA-256 hashing, SQLite queries (`tests/test_evidence_and_history.py`)
- End-to-end pipeline execution on synthetic samples (`tests/test_pipeline.py`)
- Web application routes and REST API (`tests/test_web.py`)
- End-to-end user & judge validation workflow (`tests/test_e2e_judge.py`)

---

## 5. Repository Structure

```
.
├── main.py                       # Application entry point (Web server / CLI demo)
├── requirements.txt              # Minimal project dependencies
├── README.md                     # Documentation and architecture guide
├── data/
│   ├── profiles/                 # Configurable kit profiles (JSON)
│   │   ├── sim_profile_alpha.json# Simulated Reagent Alpha (Purple proxy)
│   │   └── sim_profile_beta.json # Simulated Reagent Beta (Blue proxy)
│   ├── evidence/                 # Saved original evidence captures
│   └── demo_samples/             # Pre-packaged proxy test cases
├── src/
│   ├── config.py                 # System paths and quality thresholds
│   ├── models.py                 # Typed domain dataclasses
│   ├── quality.py                # Blur, exposure, glare, and card verification
│   ├── detection.py              # Reference card detection & ROI extraction
│   ├── calibration.py            # Patch-based illuminant gain scaling
│   ├── color.py                  # CIELAB conversion & CIEDE2000 Delta E
│   ├── engine.py                 # Multi-kit classification engine
│   ├── evidence.py               # SHA-256 hashing & evidence record assembly
│   ├── history.py                # SQLite repository and search indexing
│   ├── demo_data.py              # Prototype card and sample generator
│   └── web/                      # Flask UI and REST API
│       ├── app.py                # Web server routes
│       ├── templates/            # Responsive HTML templates
│       └── static/               # Stylesheet and client JavaScript
└── tests/                        # Full automated test suite (31 tests)
```
