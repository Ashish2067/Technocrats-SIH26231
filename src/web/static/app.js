/**
 * PS26231 MVP: Field Companion Interactive Script
 * Handles camera capture, demo sample quick-loading, GPS capture,
 * REST API communication, and dynamic telemetry rendering.
 */

let stagedImageBlob = null;
let cameraStream = null;
let lastEvidenceRecord = null;

// Initialize on profile change
function onProfileChange() {
  const select = document.getElementById("kit-profile");
  if (!select) return;
  const opt = select.options[select.selectedIndex];
  if (!opt) return;

  const timing = opt.getAttribute("data-timing") || "30";
  const posLabel = opt.getAttribute("data-pos") || "Positive";
  const negLabel = opt.getAttribute("data-neg") || "Negative";

  const timingEl = document.getElementById("meta-timing");
  const posEl = document.getElementById("meta-pos-label");
  const negEl = document.getElementById("meta-neg-label");

  if (timingEl) timingEl.textContent = timing;
  if (posEl) posEl.textContent = posLabel;
  if (negEl) negEl.textContent = negLabel;
}

// GPS Acquisition via HTML5 Geolocation
function acquireGPS() {
  const statusEl = document.getElementById("gps-status");
  const dataInput = document.getElementById("gps-data");
  const btn = document.getElementById("btn-gps");

  if (!navigator.geolocation) {
    statusEl.textContent = "GPS: Geolocation not supported by browser.";
    return;
  }

  statusEl.textContent = "Acquiring satellite fix...";
  btn.disabled = true;

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const coords = {
        latitude: Number(pos.coords.latitude.toFixed(5)),
        longitude: Number(pos.coords.longitude.toFixed(5)),
        accuracy_meters: Number(pos.coords.accuracy.toFixed(1)),
        status: "available"
      };
      dataInput.value = JSON.stringify(coords);
      statusEl.textContent = `GPS Fix: ${coords.latitude}°, ${coords.longitude}° (±${coords.accuracy_meters}m)`;
      statusEl.classList.add("active");
      btn.disabled = false;
    },
    (err) => {
      statusEl.textContent = "GPS: Fix unavailable (" + err.message + ")";
      statusEl.classList.remove("active");
      btn.disabled = false;
      dataInput.value = JSON.stringify({ status: "unavailable", error: err.message });
    },
    { timeout: 8000, enableHighAccuracy: true }
  );
}

// Toggle Input Mode (File Upload vs Live Camera)
function switchInputMode(mode) {
  const tabUpload = document.getElementById("tab-upload");
  const tabCamera = document.getElementById("tab-camera");
  const modeUpload = document.getElementById("mode-upload");
  const modeCamera = document.getElementById("mode-camera");

  if (mode === "upload") {
    tabUpload.classList.add("active");
    tabCamera.classList.remove("active");
    modeUpload.style.display = "block";
    modeCamera.style.display = "none";
    stopCamera();
  } else {
    tabCamera.classList.add("active");
    tabUpload.classList.remove("active");
    modeCamera.style.display = "block";
    modeUpload.style.display = "none";
  }
}

// WebRTC Camera Controls
async function startCamera() {
  const video = document.getElementById("camera-feed");
  const snapBtn = document.getElementById("btn-snap");
  const startBtn = document.getElementById("btn-start-camera");

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert("Live camera streaming requires a secure origin (HTTPS or localhost).\n\nWhen accessing over plain LAN HTTP, please use the Upload Photo tab to select or take a photo using your device's native camera.");
    return;
  }

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: "environment", width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    });
    video.srcObject = cameraStream;
    
    video.onloadedmetadata = () => {
      video.play().catch(() => {});
      snapBtn.disabled = false;
      startBtn.textContent = "Camera Active";
      startBtn.disabled = true;
      const telem = document.getElementById("camera-telemetry");
      if (telem) {
        telem.style.display = "flex";
        telem.innerHTML = `<span>Feed: <strong>${video.videoWidth}&times;${video.videoHeight}</strong> px</span><span>Ratio: ${(video.videoWidth / Math.max(video.videoHeight, 1)).toFixed(2)}</span>`;
      }
    };
  } catch (err) {
    alert("Camera access denied or unavailable: " + err.message + "\nPlease use file upload instead.");
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
  }
  const startBtn = document.getElementById("btn-start-camera");
  const snapBtn = document.getElementById("btn-snap");
  const telem = document.getElementById("camera-telemetry");
  if (startBtn) {
    startBtn.textContent = "Start Camera";
    startBtn.disabled = false;
  }
  if (snapBtn) snapBtn.disabled = true;
  if (telem) telem.style.display = "none";
}

function captureSnapshot() {
  const video = document.getElementById("camera-feed");
  const canvas = document.getElementById("camera-canvas");
  if (!video || !video.videoWidth) return;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob((blob) => {
    stagedImageBlob = blob;
    const telem = document.getElementById("camera-telemetry");
    if (telem) {
      telem.style.display = "flex";
      telem.innerHTML = `<span>Captured: <strong>${canvas.width}&times;${canvas.height}</strong> px</span><span>Size: <strong>${(blob.size / 1024).toFixed(0)} KB</strong></span>`;
    }
    displayImagePreview(blob, `live_snapshot_${canvas.width}x${canvas.height}.jpg`);
    document.getElementById("btn-analyze").disabled = false;
  }, "image/jpeg", 0.95);
}

// File Selected handler
function onFileSelected(input) {
  if (input.files && input.files[0]) {
    const file = input.files[0];
    stagedImageBlob = file;
    displayImagePreview(file, file.name);
    document.getElementById("btn-analyze").disabled = false;
  }
}

// Preview Staged Image
function displayImagePreview(blob, filename) {
  const container = document.getElementById("image-preview-container");
  const img = document.getElementById("image-preview");
  const nameLabel = document.getElementById("preview-filename");

  const url = URL.createObjectURL(blob);
  img.src = url;
  nameLabel.textContent = filename || "staged_test.jpg";
  container.style.display = "block";
}

// Load Pre-packaged Demo Sample
async function loadDemoSample(filename, targetProfileId) {
  try {
    const res = await fetch(`/demo-samples/${filename}`);
    if (!res.ok) throw new Error("Sample file not found");
    const blob = await res.blob();
    stagedImageBlob = blob;

    displayImagePreview(blob, filename);

    // Auto-select corresponding profile if specified
    if (targetProfileId) {
      const select = document.getElementById("kit-profile");
      if (select) {
        select.value = targetProfileId;
        onProfileChange();
      }
    }

    document.getElementById("btn-analyze").disabled = false;
  } catch (err) {
    alert("Error loading demo sample: " + err.message);
  }
}

// Execute Pipeline Analysis
async function executeAnalysis() {
  if (!stagedImageBlob) {
    alert("Please select or capture a test image first.");
    return;
  }

  const btnAnalyze = document.getElementById("btn-analyze");
  const emptyState = document.getElementById("results-empty-state");
  const loadingState = document.getElementById("results-loading");
  const resultsContent = document.getElementById("results-content");

  // UI state: loading
  btnAnalyze.disabled = true;
  emptyState.style.display = "none";
  loadingState.style.display = "block";
  resultsContent.style.display = "none";

  const operatorId = document.getElementById("operator-id").value.trim() || "OFFICER-DEFAULT";
  const profileId = document.getElementById("kit-profile").value;
  const gpsRaw = document.getElementById("gps-data").value || "{}";

  const formData = new FormData();
  formData.append("image", stagedImageBlob, "field_capture.jpg");
  formData.append("profile_id", profileId);
  formData.append("operator_id", operatorId);
  formData.append("gps", gpsRaw);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: formData
    });

    const data = await response.json();
    loadingState.style.display = "none";
    resultsContent.style.display = "flex";
    btnAnalyze.disabled = false;

    renderPipelineResults(data);
  } catch (err) {
    loadingState.style.display = "none";
    emptyState.style.display = "block";
    btnAnalyze.disabled = false;
    alert("Analysis execution error: " + err.message);
  }
}

function renderQualityPill(pillId, valId, passed, detail) {
  const pill = document.getElementById(pillId);
  const val = document.getElementById(valId);
  if (pill && val) {
    pill.className = `quality-pill ${passed ? "pass" : "fail"}`;
    val.textContent = `${passed ? "PASS" : "FAIL"} (${detail})`;
  }
}

// Render Results DOM
function renderPipelineResults(data) {
  const quality = data.quality_report;
  const isRejected = !quality.passed;

  // 1. Quality Check Card
  const badgeOverall = document.getElementById("badge-quality-overall");
  badgeOverall.textContent = quality.passed ? "PASS" : "FAIL / REJECT";
  badgeOverall.className = quality.passed ? "status-badge badge-pass" : "status-badge badge-fail";

  renderQualityPill("q-blur", "val-blur", quality.blur_passed, `Var: ${quality.blur_score}`);
  renderQualityPill("q-exposure", "val-exposure", quality.exposure_passed, quality.exposure_status.toUpperCase());
  renderQualityPill("q-glare", "val-glare", quality.glare_passed, quality.glare_detected ? "GLARE DETECTED" : "NONE");
  renderQualityPill("q-card", "val-card", quality.card_visible, quality.card_visible ? "DETECTED" : "NOT FOUND");

  const issuesList = document.getElementById("quality-issues-list");
  if (quality.issues && quality.issues.length > 0) {
    issuesList.style.display = "block";
    issuesList.innerHTML = "<strong>Recapture Guidance:</strong><ul>" +
      quality.issues.map((msg) => `<li>${msg}</li>`).join("") + "</ul>";
  } else {
    issuesList.style.display = "none";
  }

  // 2. Rejection Banner vs Classification Banner
  const rejectionBanner = document.getElementById("rejection-banner");
  const rejectionReason = document.getElementById("rejection-reason");
  const classBanner = document.getElementById("classification-banner");
  const colorCard = document.getElementById("card-color-science");
  const evidenceCard = document.getElementById("card-evidence-record");
  const techDetails = document.getElementById("card-technical-details");

  if (isRejected) {
    rejectionBanner.style.display = "block";
    rejectionReason.textContent = data.reasoning || "Image failed automated quality check. Please hold device steady and ensure reference card is clearly framed.";
    classBanner.style.display = "none";
    colorCard.style.display = "none";
    evidenceCard.style.display = "none";
    if (techDetails) techDetails.open = true;
    return;
  }

  // Successful Analysis:
  rejectionBanner.style.display = "none";
  if (techDetails) techDetails.open = false;
  const ev = data.evidence_record;
  const outcome = ev.result; // "Positive" | "Negative" | "Inconclusive"

  // Result Banner Styling
  classBanner.style.display = "flex";
  classBanner.className = `result-banner banner-${outcome.toLowerCase()}`;
  document.getElementById("result-badge").textContent = outcome.toUpperCase();
  document.getElementById("result-title").textContent = `Presumptive ${outcome}`;
  document.getElementById("result-reasoning").textContent = data.reasoning;

  // Colour Science Card
  colorCard.style.display = "block";
  const cAnalysis = ev.color_analysis;
  const calRGB = cAnalysis.calibrated_rgb;
  const swatch = document.getElementById("swatch-calibrated");
  swatch.style.backgroundColor = `rgb(${calRGB[0]}, ${calRGB[1]}, ${calRGB[2]})`;
  document.getElementById("text-calibrated-rgb").textContent = `Calibrated RGB: ${calRGB.join(", ")}`;
  document.getElementById("val-lab").textContent = `L* ${cAnalysis.calibrated_lab[0]}, a* ${cAnalysis.calibrated_lab[1]}, b* ${cAnalysis.calibrated_lab[2]}`;
  document.getElementById("val-de-pos").textContent = `${cAnalysis.delta_e_positive}`;
  document.getElementById("val-de-neg").textContent = `${cAnalysis.delta_e_negative}`;

  // Evidence Record Card
  evidenceCard.style.display = "block";
  document.getElementById("ev-test-id").textContent = ev.test_id;
  document.getElementById("ev-timestamp-utc").textContent = `${ev.timestamp_utc} (${ev.timestamp_local})`;
  document.getElementById("ev-operator").textContent = ev.operator_id;
  
  const gps = ev.gps;
  if (gps && gps.status === "available") {
    document.getElementById("ev-gps").textContent = `Lat: ${gps.latitude}°, Lon: ${gps.longitude}° (±${gps.accuracy_meters}m)`;
  } else {
    document.getElementById("ev-gps").textContent = "Unavailable at capture";
  }

  document.getElementById("ev-profile").textContent = `${ev.kit_profile.profile_id} (${ev.kit_profile.version})`;
  document.getElementById("ev-hash").textContent = ev.image_sha256;

  const evImg = document.getElementById("ev-image");
  const evImageBox = document.getElementById("ev-image-box");
  if (evImg && ev.image_filename) {
    evImg.src = `/evidence/${ev.image_filename}`;
    if (evImageBox) evImageBox.style.display = "block";
  }
  lastEvidenceRecord = ev;
}

function inspectCurrentEvidence() {
  if (lastEvidenceRecord) {
    displayRecordModal(lastEvidenceRecord);
  } else {
    alert("No evidence record available to inspect.");
  }
}

// ---------------------------------------------------------
// HISTORY PAGE FUNCTIONS
// ---------------------------------------------------------

async function fetchHistoryRecords() {
  const searchInput = document.getElementById("search-input");
  const filterProfile = document.getElementById("filter-profile");
  const filterResult = document.getElementById("filter-result");

  const query = searchInput ? searchInput.value.trim() : "";
  const profile = filterProfile ? filterProfile.value : "all";
  const result = filterResult ? filterResult.value : "all";

  const url = new URL("/api/history", window.location.origin);
  if (query) url.searchParams.append("query", query);
  if (profile !== "all") url.searchParams.append("profile", profile);
  if (result !== "all") url.searchParams.append("result", result);

  try {
    const res = await fetch(url);
    const data = await res.json();
    renderHistoryTable(data.records || []);
  } catch (err) {
    console.error("Failed to load history records", err);
  }
}

function applyFilters() {
  fetchHistoryRecords();
}

function resetFilters() {
  const searchInput = document.getElementById("search-input");
  const filterProfile = document.getElementById("filter-profile");
  const filterResult = document.getElementById("filter-result");
  if (searchInput) searchInput.value = "";
  if (filterProfile) filterProfile.value = "all";
  if (filterResult) filterResult.value = "all";
  fetchHistoryRecords();
}

function renderHistoryTable(records) {
  const tbody = document.getElementById("history-table-body");
  if (!tbody) return;

  // Cache records in map for fast, reliable lookup without inline JSON serialization
  window._historyRecords = records || [];
  window._historyRecordsMap = {};
  (records || []).forEach((r) => {
    if (r && r.test_id) {
      window._historyRecordsMap[r.test_id] = r;
    }
  });

  // Calculate statistics
  let posCount = 0;
  let negCount = 0;
  let incCount = 0;

  (records || []).forEach((r) => {
    if (r.result === "Positive") posCount++;
    else if (r.result === "Negative") negCount++;
    else incCount++;
  });

  const totalEl = document.getElementById("stat-total");
  const posEl = document.getElementById("stat-pos");
  const negEl = document.getElementById("stat-neg");
  const incEl = document.getElementById("stat-inc");

  if (totalEl) totalEl.textContent = records.length;
  if (posEl) posEl.textContent = posCount;
  if (negEl) negEl.textContent = negCount;
  if (incEl) incEl.textContent = incCount;

  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="loading-cell">No matching test records found.</td></tr>`;
    return;
  }

  tbody.innerHTML = records.map((r) => {
    const hashShort = r.image_sha256 ? `${r.image_sha256.substring(0, 10)}...${r.image_sha256.substring(58)}` : "N/A";
    const profileId = r.kit_profile ? r.kit_profile.profile_id : "UNKNOWN";

    return `
      <tr>
        <td style="font-family:var(--font-mono); font-weight:700; color:#0f172a;">${r.test_id}</td>
        <td style="font-family:var(--font-mono); font-size:0.75rem;">${r.timestamp_local || r.timestamp_utc}</td>
        <td>${r.operator_id}</td>
        <td><span style="font-family:var(--font-mono); font-size:0.75rem;">${profileId}</span></td>
        <td><span class="badge-res badge-${r.result}">${r.result}</span></td>
        <td><span class="hash-snippet" title="${r.image_sha256}">${hashShort}</span></td>
        <td>
          <button type="button" class="btn btn-secondary btn-sm btn-inspect-image" data-testid="${r.test_id}" onclick="inspectRecordById('${r.test_id}')" title="Inspect evidence image and chain of custody">Inspect Image</button>
        </td>
      </tr>
    `;
  }).join("");
}

function inspectRecordById(testId) {
  if (window._historyRecordsMap && window._historyRecordsMap[testId]) {
    displayRecordModal(window._historyRecordsMap[testId]);
    return;
  }

  // Fallback: fetch record if not currently in cached memory
  fetch(`/api/history?query=${encodeURIComponent(testId)}`)
    .then((res) => res.json())
    .then((data) => {
      const rec = (data.records || []).find((x) => x.test_id === testId);
      if (rec) {
        if (!window._historyRecordsMap) window._historyRecordsMap = {};
        window._historyRecordsMap[testId] = rec;
        displayRecordModal(rec);
      } else {
        alert("Evidence record " + testId + " not found.");
      }
    })
    .catch((err) => {
      console.error("Failed to load record for inspection:", err);
      alert("Failed to load evidence record: " + err.message);
    });
}

function inspectRecord(arg) {
  if (!arg) return;
  if (typeof arg === "string" && window._historyRecordsMap && window._historyRecordsMap[arg]) {
    displayRecordModal(window._historyRecordsMap[arg]);
    return;
  }
  try {
    const r = typeof arg === "string" ? JSON.parse(decodeURIComponent(arg)) : arg;
    displayRecordModal(r);
  } catch (e) {
    if (typeof arg === "string") {
      inspectRecordById(arg);
    } else {
      console.error("inspectRecord error:", e);
    }
  }
}

function displayRecordModal(r) {
  if (!r) return;
  const modal = document.getElementById("inspect-modal");
  const content = document.getElementById("modal-body-content");
  if (!modal || !content) return;

  const gpsText = r.gps && r.gps.status === "available"
    ? `${r.gps.latitude}°, ${r.gps.longitude}° (±${r.gps.accuracy_meters}m)`
    : "Unavailable at capture";

  const calRGB = r.color_analysis ? r.color_analysis.calibrated_rgb : [128, 128, 128];
  const swatchStyle = `width:36px;height:36px;border-radius:2px;border:1px solid #1e293b;background-color:rgb(${calRGB[0]},${calRGB[1]},${calRGB[2]})`;
  const imageSrc = r.image_filename ? `/evidence/${r.image_filename}` : "";

  content.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e2e8f0; padding-bottom:8px;">
      <div>
        <div style="font-family:var(--font-mono); font-weight:800; font-size:0.95rem; color:#0f172a;">${r.test_id}</div>
        <span class="badge-res badge-${r.result}" style="font-size:0.75rem; margin-top:3px;">PRESUMPTIVE ${(r.result || "").toUpperCase()}</span>
      </div>
      <div style="text-align:right;">
        <span style="font-size:0.65rem; color:#64748b; display:block; text-transform:uppercase; font-family:var(--font-mono);">Swatch</span>
        <div style="${swatchStyle}" title="Calibrated Reaction Swatch"></div>
      </div>
    </div>

    <div class="evidence-table" style="background:#f8fafc; padding:10px 12px; border-radius:2px; border:1px solid #e2e8f0;">
      <div class="ev-row"><span class="ev-key">Recorded UTC:</span> <span class="ev-val">${r.timestamp_utc || "N/A"}</span></div>
      <div class="ev-row"><span class="ev-key">Recorded Local:</span> <span class="ev-val">${r.timestamp_local || "N/A"}</span></div>
      <div class="ev-row"><span class="ev-key">Operator ID:</span> <span class="ev-val">${r.operator_id || "N/A"}</span></div>
      <div class="ev-row"><span class="ev-key">GPS Telemetry:</span> <span class="ev-val">${gpsText}</span></div>
      <div class="ev-row"><span class="ev-key">Kit Profile:</span> <span class="ev-val">${r.kit_profile ? `${r.kit_profile.profile_id} (${r.kit_profile.version})` : "N/A"}</span></div>
      ${r.color_analysis ? `
        <div class="ev-row"><span class="ev-key">CIELAB Coordinates:</span> <span class="ev-val">${(r.color_analysis.calibrated_lab || []).join(", ")}</span></div>
        <div class="ev-row"><span class="ev-key">&Delta;E to Positive Target:</span> <span class="ev-val">${r.color_analysis.delta_e_positive ?? "N/A"}</span></div>
        <div class="ev-row"><span class="ev-key">&Delta;E to Negative Target:</span> <span class="ev-val">${r.color_analysis.delta_e_negative ?? "N/A"}</span></div>
      ` : ""}
    </div>

    <div class="ev-hash-row">
      <span class="ev-key">Cryptographic SHA-256 Image Integrity Hash:</span>
      <div class="hash-box">
        <code style="word-break:break-all;">${r.image_sha256 || "N/A"}</code>
      </div>
    </div>

    <div style="margin-top:8px;">
      <span class="ev-key" style="display:block; margin-bottom:4px;">Captured Evidence Image:</span>
      <div style="width:100%; border-radius:2px; border:1px solid #cbd5e1; overflow:hidden; background:#0f172a; text-align:center;">
        ${imageSrc ? `
          <img src="${imageSrc}" alt="Evidence for ${r.test_id}" class="evidence-image modal-evidence-image" style="width:100%; max-height:55vh; object-fit:contain; display:block; margin:0 auto;" onerror="this.onerror=null; this.alt='Image file not found on disk'; this.style.color='#fff'; this.style.padding='20px';">
        ` : `
          <div style="color:#94a3b8; padding:30px; font-size:0.8rem;">No evidence image recorded</div>
        `}
      </div>
      ${imageSrc ? `
        <div style="margin-top:6px; display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:0.75rem; font-family:var(--font-mono); color:var(--text-light);">${r.image_filename}</span>
          <a href="${imageSrc}" target="_blank" rel="noopener noreferrer" class="btn-link-action" style="font-size:0.75rem;">Open Full Size &nearr;</a>
        </div>
      ` : ""}
    </div>

    ${r.disclaimer ? `<small style="color:#64748b; font-size:0.7rem; display:block; border-top:1px solid #f1f5f9; padding-top:6px;">${r.disclaimer}</small>` : ""}
  `;

  modal.style.display = "flex";
  document.body.style.overflow = "hidden";
}

function closeModal() {
  const modal = document.getElementById("inspect-modal");
  if (modal) modal.style.display = "none";
  document.body.style.overflow = "";
}

// Global escape key listener to close modal
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeModal();
  }
});

function copyHash() {
  const hashEl = document.getElementById("ev-hash");
  if (!hashEl) return;
  const hash = hashEl.textContent.trim();
  if (!hash || hash === "-") return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(hash).then(() => {
      const btn = document.querySelector(".btn-copy");
      if (btn) {
        const orig = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => { btn.textContent = orig; }, 1500);
      }
    }).catch(() => {
      prompt("SHA-256 Digest:", hash);
    });
  } else {
    prompt("SHA-256 Digest:", hash);
  }
}
