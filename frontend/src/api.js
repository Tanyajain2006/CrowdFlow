const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function request(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed with status ${response.status}`);
  }
  return response.status === 204 ? null : response.json();
}

export function getHealth() {
  return request("/health");
}

export function uploadVideo(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/video/upload", { method: "POST", body: form });
}

export function startAnalysis(videoId, frameInterval = 10, zones = null) {
  return request("/analysis/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_id: videoId,
      frame_interval: frameInterval,
      zones,
    }),
  });
}

export function getAnalysisStatus(analysisId) {
  const query = analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : "";
  return request(`/analysis/status${query}`);
}

export function getZones(analysisId) {
  const query = analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : "";
  return request(`/zones/current${query}`);
}

export function configureZones(analysisId, zones) {
  return request(`/zones/configure?analysis_id=${encodeURIComponent(analysisId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ zones }),
  });
}

export function getPredictions(analysisId) {
  const query = analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : "";
  return request(`/predictions${query}`);
}

export function getGraph(analysisId) {
  const query = analysisId ? `?analysis_id=${encodeURIComponent(analysisId)}` : "";
  return request(`/graph${query}`);
}

export function detectedFrameUrl(analysisId) {
  return `${API_BASE}/analysis/frame/${encodeURIComponent(analysisId)}`;
}

export function analysisWebSocketUrl(analysisId) {
  return `${API_BASE.replace(/^http/, "ws")}/ws/analysis/${encodeURIComponent(analysisId)}`;
}

export function getTrajectories(analysisId) {
  return request(`/analysis/trajectories/${encodeURIComponent(analysisId)}`);
}
