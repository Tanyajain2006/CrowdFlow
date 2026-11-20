from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from .config import DATABASE_PATH
from .persistence import SQLitePersistence
from .schemas import AnalysisProgress, AnalysisStatus, VideoMetadata, ZoneDefinition


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.persistence = SQLitePersistence(DATABASE_PATH)
        self.videos: dict[str, VideoMetadata] = self.persistence.load_videos()
        self.jobs: dict[str, AnalysisProgress] = self.persistence.load_analyses()
        self.video_id_by_path: dict[str, str] = {}
        self.zones: dict[str, list[ZoneDefinition]] = self.persistence.load_zones()
        (
            self.zone_results,
            self.graph_results,
            self.predictions,
            loaded_trajectories,
        ) = self.persistence.load_results()
        self.analysis_video: dict[str, str] = {}
        self.detected_frames: dict[str, str] = {}
        self.track_history: dict[str, dict[int, list[dict[str, Any]]]] = {}
        for analysis_id, trajectory in loaded_trajectories.items():
            self.track_history[analysis_id] = trajectory
        for video in self.videos.values():
            self.video_id_by_path[video.path] = video.video_id
        for analysis_id, job in self.jobs.items():
            self.analysis_video[analysis_id] = job.video_id
            if job.detected_frame_url:
                frame_name = job.detected_frame_url.rsplit("/", 1)[-1]
                frame_path = DATABASE_PATH.parent / "detected" / frame_name
                if frame_path.exists():
                    self.detected_frames[analysis_id] = str(frame_path)
        for analysis_id, job in list(self.jobs.items()):
            if job.status in (AnalysisStatus.QUEUED, AnalysisStatus.PROCESSING):
                self.jobs[analysis_id] = job.model_copy(
                    update={
                        "status": AnalysisStatus.FAILED,
                        "error": "Analysis process stopped before completion",
                        "message": "Analysis interrupted by backend restart",
                        "updated_at": utc_now(),
                    }
                )
                self.persistence.save_analysis(self.jobs[analysis_id])

    def create_video(self, path: Path, filename: str, size_bytes: int) -> VideoMetadata:
        video_id = str(uuid4())
        metadata = VideoMetadata(
            video_id=video_id,
            filename=filename,
            path=str(path.resolve()),
            size_bytes=size_bytes,
        )
        with self._lock:
            self.videos[video_id] = metadata
            self.video_id_by_path[str(path.resolve())] = video_id
            self.persistence.save_video(metadata)
        return metadata

    def update_video(self, video_id: str, **metadata: Any) -> VideoMetadata:
        with self._lock:
            current = self.videos[video_id]
            updated = current.model_copy(update=metadata)
            self.videos[video_id] = updated
            self.persistence.save_video(updated)
            return updated

    def get_video(self, video_id: str) -> VideoMetadata | None:
        with self._lock:
            return self.videos.get(video_id)

    def create_job(self, video_id: str) -> AnalysisProgress:
        analysis_id = str(uuid4())
        progress = AnalysisProgress(
            analysis_id=analysis_id,
            video_id=video_id,
            status=AnalysisStatus.QUEUED,
            updated_at=utc_now(),
            message="Analysis queued",
        )
        with self._lock:
            self.jobs[analysis_id] = progress
            self.analysis_video[analysis_id] = video_id
            self.persistence.save_analysis(progress)
        return progress

    def update_job(self, analysis_id: str, **updates: Any) -> AnalysisProgress:
        with self._lock:
            current = self.jobs[analysis_id]
            updated = current.model_copy(
                update={**updates, "updated_at": utc_now()}
            )
            self.jobs[analysis_id] = updated
            self.persistence.save_analysis(updated)
            return updated

    def get_job(self, analysis_id: str) -> AnalysisProgress | None:
        with self._lock:
            return self.jobs.get(analysis_id)

    def latest_job(self) -> AnalysisProgress | None:
        with self._lock:
            if not self.jobs:
                return None
            return max(self.jobs.values(), key=lambda job: job.updated_at)

    def save_zones(self, analysis_id: str, zones: list[ZoneDefinition]) -> None:
        with self._lock:
            self.zones[analysis_id] = zones
            self.persistence.save_zones(analysis_id, zones)

    def save_results(
        self,
        analysis_id: str,
        statistics: list[dict[str, Any]],
        graph: dict[str, Any],
        predictions: dict[str, Any],
        trajectories: dict[int, list[dict[str, Any]]] | None = None,
    ) -> None:
        with self._lock:
            self.zone_results[analysis_id] = statistics
            self.graph_results[analysis_id] = graph
            self.predictions[analysis_id] = predictions
            serializable_trajectories: dict[str, Any] | None = None
            if trajectories is not None:
                serializable_trajectories = {
                    str(track_id): points
                    for track_id, points in trajectories.items()
                }
                self.track_history[analysis_id] = {
                    int(track_id): points
                    for track_id, points in serializable_trajectories.items()
                }
            self.persistence.save_results(
                analysis_id,
                statistics,
                graph,
                predictions,
                serializable_trajectories,
            )


store = AnalysisStore()

