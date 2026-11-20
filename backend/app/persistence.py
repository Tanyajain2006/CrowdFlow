import json
import sqlite3
from pathlib import Path
from typing import Any

from .schemas import AnalysisProgress, VideoMetadata, ZoneDefinition


class SQLitePersistence:
    """Small SQLite persistence layer for Phase 1 process restarts."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    video_id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    fps REAL,
                    frame_count INTEGER,
                    width INTEGER,
                    height INTEGER,
                    duration_seconds REAL
                );
                CREATE TABLE IF NOT EXISTS analyses (
                    analysis_id TEXT PRIMARY KEY,
                    video_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress_percent REAL NOT NULL,
                    processed_frames INTEGER NOT NULL,
                    total_frames INTEGER NOT NULL,
                    current_frame INTEGER,
                    detected_count INTEGER NOT NULL,
                    message TEXT NOT NULL,
                    error TEXT,
                    detected_frame_url TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS zones (
                    analysis_id TEXT NOT NULL,
                    zone_id TEXT NOT NULL,
                    zone_json TEXT NOT NULL,
                    PRIMARY KEY (analysis_id, zone_id)
                );
                CREATE TABLE IF NOT EXISTS statistics (
                    analysis_id TEXT PRIMARY KEY,
                    statistics_json TEXT NOT NULL,
                    graph_json TEXT NOT NULL,
                    predictions_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS trajectories (
                    analysis_id TEXT PRIMARY KEY,
                    trajectory_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def save_video(self, video: VideoMetadata) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO videos
                   (video_id, filename, path, size_bytes, fps, frame_count, width, height, duration_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    video.video_id,
                    video.filename,
                    video.path,
                    video.size_bytes,
                    video.fps,
                    video.frame_count,
                    video.width,
                    video.height,
                    video.duration_seconds,
                ),
            )

    def load_videos(self) -> dict[str, VideoMetadata]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM videos").fetchall()
        return {
            row["video_id"]: VideoMetadata(
                video_id=row["video_id"],
                filename=row["filename"],
                path=row["path"],
                size_bytes=row["size_bytes"],
                fps=row["fps"],
                frame_count=row["frame_count"],
                width=row["width"],
                height=row["height"],
                duration_seconds=row["duration_seconds"],
            )
            for row in rows
        }

    def save_analysis(self, job: AnalysisProgress) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO analyses
                   (analysis_id, video_id, status, progress_percent, processed_frames,
                    total_frames, current_frame, detected_count, message, error,
                    detected_frame_url, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job.analysis_id,
                    job.video_id,
                    job.status.value,
                    job.progress_percent,
                    job.processed_frames,
                    job.total_frames,
                    job.current_frame,
                    job.detected_count,
                    job.message,
                    job.error,
                    job.detected_frame_url,
                    job.updated_at.isoformat(),
                ),
            )

    def load_analyses(self) -> dict[str, AnalysisProgress]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM analyses").fetchall()
        jobs: dict[str, AnalysisProgress] = {}
        for row in rows:
            jobs[row["analysis_id"]] = AnalysisProgress(
                analysis_id=row["analysis_id"],
                video_id=row["video_id"],
                status=row["status"],
                progress_percent=row["progress_percent"],
                processed_frames=row["processed_frames"],
                total_frames=row["total_frames"],
                current_frame=row["current_frame"],
                detected_count=row["detected_count"],
                message=row["message"],
                error=row["error"],
                detected_frame_url=row["detected_frame_url"],
                updated_at=row["updated_at"],
            )
        return jobs

    def save_zones(self, analysis_id: str, zones: list[ZoneDefinition]) -> None:
        with self._connection() as connection:
            connection.execute("DELETE FROM zones WHERE analysis_id = ?", (analysis_id,))
            for zone in zones:
                connection.execute(
                    "INSERT INTO zones (analysis_id, zone_id, zone_json) VALUES (?, ?, ?)",
                    (analysis_id, zone.zone_id, zone.model_dump_json()),
                )

    def load_zones(self) -> dict[str, list[ZoneDefinition]]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM zones").fetchall()
        zones: dict[str, list[ZoneDefinition]] = {}
        for row in rows:
            zones.setdefault(row["analysis_id"], []).append(
                ZoneDefinition.model_validate_json(row["zone_json"])
            )
        return zones

    def save_results(
        self,
        analysis_id: str,
        statistics: list[dict[str, Any]],
        graph: dict[str, Any],
        predictions: dict[str, Any],
        trajectories: dict[str, Any] | None = None,
    ) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO statistics
                   (analysis_id, statistics_json, graph_json, predictions_json, updated_at)
                   VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (
                    analysis_id,
                    json.dumps(statistics),
                    json.dumps(graph),
                    json.dumps(predictions),
                ),
            )
            if trajectories is not None:
                connection.execute(
                    """INSERT OR REPLACE INTO trajectories
                       (analysis_id, trajectory_json, updated_at)
                       VALUES (?, ?, CURRENT_TIMESTAMP)""",
                    (analysis_id, json.dumps(trajectories)),
                )

    def load_results(
        self,
    ) -> tuple[
        dict[str, list[dict[str, Any]]],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
        dict[str, dict[str, Any]],
    ]:
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM statistics").fetchall()
            trajectory_rows = connection.execute("SELECT * FROM trajectories").fetchall()
        statistics: dict[str, list[dict[str, Any]]] = {}
        graphs: dict[str, dict[str, Any]] = {}
        predictions: dict[str, dict[str, Any]] = {}
        trajectories: dict[str, dict[str, Any]] = {}
        for row in rows:
            statistics[row["analysis_id"]] = json.loads(row["statistics_json"])
            graphs[row["analysis_id"]] = json.loads(row["graph_json"])
            predictions[row["analysis_id"]] = json.loads(row["predictions_json"])
        for row in trajectory_rows:
            trajectories[row["analysis_id"]] = json.loads(row["trajectory_json"])
        return statistics, graphs, predictions, trajectories
