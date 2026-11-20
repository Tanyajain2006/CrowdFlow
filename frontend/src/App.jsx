import { useEffect, useMemo, useState } from "react";
import {
  BarChart,
  Bar,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  configureZones,
  detectedFrameUrl,
  getHealth,
  getGraph,
  getTrajectories,
  getPredictions,
  getZones,
  getAnalysisStatus,
  analysisWebSocketUrl,
  startAnalysis,
  uploadVideo,
} from "./api";

const sections = [
  { label: "Overview", icon: "◫" },
  { label: "Video Upload", icon: "⌁" },
  { label: "Detection Monitor", icon: "◎" },
  { label: "Zone Intelligence", icon: "▦" },
  { label: "Prediction Monitor", icon: "↗" },
  { label: "Venue Graph", icon: "⌬" },
  { label: "Analysis Status", icon: "◷" },
];

function App() {
  const [active, setActive] = useState("Overview");
  const [file, setFile] = useState(null);
  const [video, setVideo] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [status, setStatus] = useState(null);
  const [zoneData, setZoneData] = useState({ zones: [], statistics: [] });
  const [predictions, setPredictions] = useState(null);
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [backendHealthy, setBackendHealthy] = useState(null);
  const [zoneJson, setZoneJson] = useState("");
  const [trackCount, setTrackCount] = useState(0);

  useEffect(() => {
    getHealth()
      .then(() => setBackendHealthy(true))
      .catch(() => setBackendHealthy(false));
  }, []);

  useEffect(() => {
    if (!analysis) return undefined;
    let stopped = false;
    const socket = new WebSocket(analysisWebSocketUrl(analysis.analysis_id));

    socket.onmessage = (event) => {
      if (stopped) return;
      try {
        const update = JSON.parse(event.data);
        setStatus((current) => ({ ...current, ...update }));
        if (update.zone_statistics) {
          setZoneData((current) => ({ ...current, statistics: update.zone_statistics }));
        }
        if (update.predictions) setPredictions(update.predictions);
      } catch {
        // Ignore malformed socket frames; REST polling remains the recovery path.
      }
    };

    const refresh = async () => {
      try {
        const current = await getAnalysisStatus(analysis.analysis_id);
        if (stopped) return;
        setStatus(current);
        if (current.status === "completed") {
          const [zones, forecast, venueGraph, trajectories] = await Promise.all([
            getZones(analysis.analysis_id),
            getPredictions(analysis.analysis_id),
            getGraph(analysis.analysis_id),
            getTrajectories(analysis.analysis_id),
          ]);
          if (!stopped) {
            setZoneData(zones);
            setPredictions(forecast);
            setGraph(venueGraph);
            setTrackCount(trajectories.track_count);
          }
        } else if (current.status === "processing" || current.status === "queued") {
          const zones = await getZones(analysis.analysis_id).catch(() => null);
          if (!stopped && zones) setZoneData(zones);
        }
      } catch (requestError) {
        if (!stopped) setError(requestError.message);
      }
    };

    refresh();
    const interval = window.setInterval(refresh, 1500);
    return () => {
      stopped = true;
      window.clearInterval(interval);
      socket.close();
    };
  }, [analysis]);

  const handleUpload = async () => {
    if (!file) {
      setError("Select a recorded video first.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await uploadVideo(file);
      setVideo(result.video);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const handleStart = async () => {
    if (!video) {
      setError("Upload a video before starting analysis.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      let zones = null;
      if (zoneJson.trim()) {
        zones = JSON.parse(zoneJson);
        if (!Array.isArray(zones) || zones.length === 0) {
          throw new Error("Zone JSON must be a non-empty array.");
        }
      }
      const result = await startAnalysis(video.video_id, 10, zones);
      setAnalysis(result);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const handleConfigureZones = async () => {
    if (!analysis) {
      setError("Start an analysis before configuring zones.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const zones = JSON.parse(zoneJson);
      if (!Array.isArray(zones) || zones.length === 0) {
        throw new Error("Zone JSON must be a non-empty array.");
      }
      await configureZones(analysis.analysis_id, zones);
      const zonesResult = await getZones(analysis.analysis_id);
      setZoneData(zonesResult);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const forecastRows = useMemo(() => {
    if (!predictions) return [];
    return predictions.forecasts.map((item) => ({
      zone: item.zone_id,
      horizon: item.horizon_seconds,
      observed: item.observed_occupancy,
      predicted: item.predicted_occupancy,
      risk: item.risk,
      reliability: item.reliability,
    }));
  }, [predictions]);

  const statistics = zoneData.statistics || [];

  return (
    <div className="shell">
      <aside>
        <div className="brand">CROWDFLOW</div>
        <nav>
          {sections.map((item) => (
            <button
              key={item.label}
              className={active === item.label ? "active" : ""}
              onClick={() => setActive(item.label)}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <main>
        <header>
          <div>
            <p className="eyebrow">Phase 1 Operations</p>
            <h1>{active}</h1>
          </div>
          {status && <span className={`status ${status.status}`}>{status.status}</span>}
          {!status && backendHealthy !== null && (
            <span className={`status ${backendHealthy ? "completed" : "failed"}`}>
              API {backendHealthy ? "connected" : "offline"}
            </span>
          )}
        </header>

        {error && <div className="error">{error}</div>}

        {active === "Overview" && (
          <section className="overview">
            <div className="hero">
              <div>
                <p className="hero-kicker">CROWDFLOW CONTROL CENTER</p>
                <h2>Turn video observations into early congestion signals.</h2>
                <p>
                  Upload footage, detect and track people, configure venue zones,
                  and monitor 10 / 20 / 30-second forecasts.
                </p>
              </div>
              <div className="hero-orbit" aria-hidden="true">
                <span />
                <span />
                <strong>{status?.detected_count ?? 0}</strong>
                <small>detected</small>
              </div>
            </div>

            <div className="grid cards">
              <article className="metric-card accent-blue">
                <div className="metric-icon">▶</div>
                <span>Uploaded video</span>
                <strong>{video ? video.filename : "No video selected"}</strong>
              </article>
              <article className="metric-card accent-violet">
                <div className="metric-icon">◷</div>
                <span>Analysis</span>
                <strong>{status ? status.status : "Not started"}</strong>
              </article>
              <article className="metric-card accent-cyan">
                <div className="metric-icon">◎</div>
                <span>Latest frame detections</span>
                <strong>{status?.detected_count ?? 0}</strong>
              </article>
              <article className="metric-card accent-red">
                <div className="metric-icon">!</div>
                <span>Bottlenecks</span>
                <strong>{graph?.bottlenecks?.length ?? 0}</strong>
              </article>
              <article className="metric-card accent-green">
                <div className="metric-icon">⌁</div>
                <span>Persistent tracks</span>
                <strong>{trackCount}</strong>
              </article>
            </div>
          </section>
        )}

        {active === "Video Upload" && (
          <section className="panel">
            <h2>Recorded Video Analysis</h2>
            <p>Upload an MP4, AVI, MOV, MKV, or WebM recording.</p>
            <input
              type="file"
              accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,video/webm"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
            />
            <div className="actions">
              <button disabled={busy} onClick={handleUpload}>Upload video</button>
              <button disabled={busy || !video} onClick={handleStart}>Start analysis</button>
            </div>
            {video && (
              <dl>
                <dt>Filename</dt><dd>{video.filename}</dd>
                <dt>Resolution</dt><dd>{video.width} x {video.height}</dd>
                <dt>FPS</dt><dd>{video.fps?.toFixed(2)}</dd>
                <dt>Duration</dt><dd>{video.duration_seconds?.toFixed(2)} seconds</dd>
              </dl>
            )}
          </section>
        )}

        {active === "Detection Monitor" && (
          <section className="panel">
            <h2>Tracked Pedestrians</h2>
            {analysis ? (
              <img
                className="detection-frame"
                src={`${detectedFrameUrl(analysis.analysis_id)}?t=${status?.updated_at || ""}`}
                alt="Latest YOLO and ByteTrack detection frame"
              />
            ) : <p>No analysis has been started.</p>}
          </section>
        )}

        {active === "Zone Intelligence" && (
          <section className="panel">
            <h2>Zone Statistics</h2>
            <p>
              Optionally define zones as JSON polygons. Coordinates use image-pixel values.
            </p>
            <textarea
              className="zone-editor"
              value={zoneJson}
              onChange={(event) => setZoneJson(event.target.value)}
              placeholder='[{"zone_id":"entrance","name":"Entrance","polygon":[[0,0],[100,0],[100,100],[0,100]],"capacity":100}]'
            />
            <button disabled={busy || !analysis} onClick={handleConfigureZones}>
              Save zones
            </button>
            {statistics.length ? (
              <ResponsiveContainer width="100%" height={340}>
                <BarChart data={statistics}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="occupancy" fill="#2563eb" name="Observed occupancy" />
                  <Bar dataKey="capacity" fill="#94a3b8" name="Capacity" />
                </BarChart>
              </ResponsiveContainer>
            ) : <p>Zone statistics appear after the first processed frame.</p>}
          </section>
        )}

        {active === "Prediction Monitor" && (
          <section className="panel">
            <h2>Deterministic 10 / 20 / 30 Second Forecasts</h2>
            {forecastRows.length ? (
              <>
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={forecastRows}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="horizon" />
                    <YAxis />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="observed" stroke="#64748b" name="Observed" />
                    <Line type="monotone" dataKey="predicted" stroke="#dc2626" name="Predicted" />
                  </LineChart>
                </ResponsiveContainer>
                <div className="forecast-list">
                  {forecastRows.map((item, index) => (
                    <article key={`${item.zone}-${item.horizon}-${index}`}>
                      <strong>{item.zone}</strong>
                      <span>{item.horizon}s predicted: {item.predicted}</span>
                      <span className={`risk ${item.risk.toLowerCase()}`}>{item.risk}</span>
                      <small>Reliability: {item.reliability}</small>
                    </article>
                  ))}
                </div>
              </>
            ) : <p>Predictions appear after the CV pipeline produces zone observations.</p>}
          </section>
        )}

        {active === "Venue Graph" && (
          <section className="panel">
            <h2>Venue Graph</h2>
            {graph ? (
              <div className="graph-list">
                {graph.nodes.map((node) => (
                  <article key={node.id}>
                    <strong>{node.label}</strong>
                    <span>{node.occupancy} / {node.capacity}</span>
                  </article>
                ))}
                <p><strong>Bottlenecks:</strong> {graph.bottlenecks.length ? graph.bottlenecks.join(", ") : "None observed"}</p>
              </div>
            ) : <p>The venue graph appears after the first processed frame.</p>}
          </section>
        )}

        {active === "Analysis Status" && (
          <section className="panel">
            <h2>Processing Status</h2>
            {status ? (
              <>
                <div className="progress"><span style={{ width: `${status.progress_percent}%` }} /></div>
                <dl>
                  <dt>Status</dt><dd>{status.status}</dd>
                  <dt>Progress</dt><dd>{status.progress_percent.toFixed(1)}%</dd>
                  <dt>Processed frames</dt><dd>{status.processed_frames} / {status.total_frames}</dd>
                  <dt>Detected count</dt><dd>{status.detected_count}</dd>
                  <dt>Message</dt><dd>{status.message}</dd>
                  {status.error && <><dt>Error</dt><dd>{status.error}</dd></>}
                </dl>
              </>
            ) : <p>No analysis job is available.</p>}
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
