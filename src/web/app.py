"""
Flask Web Application for PS26231 MVP: Digital Companion for Field Drug Testing.
Serves responsive UI, REST API endpoints, image evidence storage, and demo samples.
"""
import os
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory
from src.config import EVIDENCE_DIR, DEMO_SAMPLES_DIR, STANDARD_DISCLAIMER
from src.engine import list_available_profiles, get_kit_profile
from src.pipeline import run_pipeline
from src.history import search_records, get_record_by_id, init_database
from src.demo_data import generate_all_demo_samples

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static")
)

# Initialize DB and demo samples on start
init_database()
generate_all_demo_samples()


@app.route("/")
def index():
    profiles = [p.to_dict() for p in list_available_profiles()]
    return render_template("index.html", profiles=profiles, disclaimer=STANDARD_DISCLAIMER)


@app.route("/history")
def history_page():
    profiles = [p.to_dict() for p in list_available_profiles()]
    return render_template("history.html", profiles=profiles, disclaimer=STANDARD_DISCLAIMER)


@app.route("/reference-card")
def reference_card_page():
    return render_template("card.html", disclaimer=STANDARD_DISCLAIMER)


@app.route("/api/profiles", methods=["GET"])
def api_get_profiles():
    profiles = [p.to_dict() for p in list_available_profiles()]
    return jsonify({"success": True, "profiles": profiles})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Receives image (uploaded file or camera capture blob), kit profile ID, operator ID, and GPS.
    Runs the full 12-step pipeline and returns execution result with digital evidence record.
    """
    profile_id = request.form.get("profile_id", "SIM-PROFILE-ALPHA")
    operator_id = request.form.get("operator_id", "FIELD-OP-01")
    gps_raw = request.form.get("gps", "{}")

    try:
        gps_data = json.loads(gps_raw)
    except Exception:
        gps_data = {}

    profile = get_kit_profile(profile_id)
    if not profile:
        return jsonify({
            "success": False,
            "error": f"Unknown kit profile ID: {profile_id}"
        }), 400

    # Get image data from uploaded file
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": "No image file provided in request."
        }), 400

    image_file = request.files["image"]
    image_bytes = image_file.read()

    if not image_bytes:
        return jsonify({
            "success": False,
            "error": "Uploaded image file is empty."
        }), 400

    # Run the unified PS26231 pipeline
    result = run_pipeline(
        image_bytes=image_bytes,
        profile=profile,
        operator_id=operator_id,
        gps_data=gps_data,
        persist=True
    )

    return jsonify(result.to_dict())


@app.route("/api/history", methods=["GET"])
def api_history():
    query = request.args.get("query", None)
    result_filter = request.args.get("result", None)
    profile_filter = request.args.get("profile", None)

    records = search_records(
        query=query,
        result_filter=result_filter,
        profile_filter=profile_filter,
        limit=100
    )
    return jsonify({"success": True, "count": len(records), "records": records})


@app.route("/api/history/<test_id>", methods=["GET"])
def api_history_detail(test_id):
    record = get_record_by_id(test_id)
    if not record:
        return jsonify({"success": False, "error": "Record not found"}), 404
    return jsonify({"success": True, "record": record})


@app.route("/evidence/<filename>")
def serve_evidence_image(filename):
    return send_from_directory(str(EVIDENCE_DIR), filename)


@app.route("/demo-samples/<filename>")
def serve_demo_sample(filename):
    return send_from_directory(str(DEMO_SAMPLES_DIR), filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
