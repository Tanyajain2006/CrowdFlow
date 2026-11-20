import cv2
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..config import (
    FRAME_INTERVAL,
    OUTPUT_DIR,
    YOLO_CONFIDENCE,
    YOLO_DEVICE,
    YOLO_MODEL,
)
from ..schemas import AnalysisStatus
from ..state import store
from ..ws import manager
from .detection import PedestrianDetector
from .forecasting import calculate_forecasts
from .venue_graph import build_venue_graph
from .zone_analytics import ZoneAnalytics, default_zones


def broadcast_update(analysis_id: str, payload: dict) -> None:
    """Send a live update without tying CV processing to FastAPI request context."""
    try:
        asyncio.run(manager.broadcast(analysis_id, payload))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(manager.broadcast(analysis_id, payload))
        finally:
            loop.close()


def run_analysis(
    analysis_id: str,
    video_id: str,
    frame_interval: int = FRAME_INTERVAL,
) -> None:
    """Run recorded-video detection, analytics, graph building, and forecasting."""
    try:
        store.update_job(
            analysis_id,
            status=AnalysisStatus.PROCESSING,
            progress_percent=0.0,
            processed_frames=0,
            message="Loading pretrained YOLO model",
        )
        broadcast_update(
            analysis_id,
            {"status": "processing", "progress_percent": 0.0, "message": "Loading pretrained YOLO model"},
        )

        video = store.get_video(video_id)
        if video is None:
            raise RuntimeError("Uploaded video metadata is unavailable")

        capture = cv2.VideoCapture(video.path)
        if not capture.isOpened():
            raise RuntimeError("The uploaded video could not be opened")

        fps = float(capture.get(cv2.CAP_PROP_FPS)) or 30.0
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        store.update_job(
            analysis_id,
            total_frames=max(1, (frame_count + frame_interval - 1) // frame_interval),
        )

        zones = store.zones.get(analysis_id)
        if not zones:
            zones = default_zones(width, height)
            store.save_zones(analysis_id, zones)

        analytics = ZoneAnalytics(zones)
        detector = PedestrianDetector(YOLO_MODEL, YOLO_CONFIDENCE, YOLO_DEVICE)
        detector.load()

        detected_dir = OUTPUT_DIR / "detected"
        detected_dir.mkdir(parents=True, exist_ok=True)
        latest_frame_path: Path | None = None

        pending_forecasts: list[dict] = []
        evaluation_errors: list[dict] = []
        previous_track_ids: set[int] = set()
        stable_track_samples = 0
        track_samples = 0
        detection_samples = 0
        final_statistics: list[dict] = []
        final_graph: dict | None = None
        final_predictions: dict | None = None
        trajectories: dict[int, list[dict]] = {}
        processed = 0
        frame_index = 0

        while True:
            ok, frame = capture.read()
            if not ok:
                break

            if frame_index % frame_interval == 0:
                elapsed_seconds = frame_index / fps
                tracks, annotated = detector.process_frame(frame)
                processed += 1
                detection_samples += len(tracks)
                track_samples += 1

                current_ids = {int(track["track_id"]) for track in tracks}
                for track in tracks:
                    track_id = int(track["track_id"])
                    trajectories.setdefault(track_id, []).append(
                        {
                            "frame_index": frame_index,
                            "elapsed_seconds": round(elapsed_seconds, 3),
                            "x": round(float(track["representative_x"]), 2),
                            "y": round(float(track["representative_y"]), 2),
                            "confidence": round(float(track["confidence"]), 3),
                        }
                    )
                stable_track_count = len(current_ids & previous_track_ids)
                stable_track_samples += stable_track_count
                previous_track_ids = current_ids

                final_statistics = analytics.update(tracks, elapsed_seconds)
                latest_frame_path = detected_dir / f"{analysis_id}.jpg"
                cv2.imwrite(str(latest_frame_path), annotated)
                frame_url = f"/storage/detected/{analysis_id}.jpg"
                store.detected_frames[analysis_id] = str(latest_frame_path)

                graph = build_venue_graph(zones, final_statistics)
                final_graph = graph
                store.graph_results[analysis_id] = graph

                for evaluated in list(pending_forecasts):
                    if elapsed_seconds + 0.001 >= evaluated["_due_elapsed"]:
                        observed = next(
                            (
                                item["occupancy"]
                                for item in final_statistics
                                if item["zone_id"] == evaluated["zone_id"]
                            ),
                            0,
                        )
                        absolute_error = abs(observed - evaluated["predicted_occupancy"])
                        evaluation_errors.append(
                            {
                                "zone_id": evaluated["zone_id"],
                                "horizon_seconds": evaluated["horizon_seconds"],
                                "predicted_occupancy": evaluated["predicted_occupancy"],
                                "observed_occupancy": observed,
                                "absolute_error": round(absolute_error, 2),
                                "evaluated_at_elapsed_seconds": round(elapsed_seconds, 2),
                            }
                        )
                        pending_forecasts.remove(evaluated)

                track_visibility = min(1.0, stable_track_samples / max(track_samples * 5, 1))
                detection_strength = min(1.0, detection_samples / max(track_samples * 10, 1))
                data_quality = max(0.0, min(1.0, 0.5 * track_visibility + 0.5 * detection_strength))

                affected_by: dict[str, list[str]] = {
                    zone.zone_id: []
                    for zone in zones
                }
                for source_zone, neighboring_zones in graph["affected_zones"].items():
                    for neighboring_zone in neighboring_zones:
                        affected_by.setdefault(neighboring_zone, []).append(source_zone)
                forecast_result = calculate_forecasts(
                    final_statistics,
                    analytics.zone_occupancy_history,
                    analytics.zone_flow_history,
                    datetime.now(timezone.utc),
                    data_quality,
                    affected_by,
                )

                for forecast in forecast_result["forecasts"]:
                    pending_forecasts.append(
                        {
                            **forecast,
                            "_due_elapsed": elapsed_seconds + forecast["horizon_seconds"],
                        }
                    )

                final_predictions = {
                    "analysis_id": analysis_id,
                    "horizon_seconds": [10, 20, 30],
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "forecasts": forecast_result["forecasts"],
                    "evaluation": {
                        "status": "collecting" if pending_forecasts else "evaluated",
                        "evaluated_count": len(evaluation_errors),
                        "mean_absolute_error": (
                            round(
                                sum(item["absolute_error"] for item in evaluation_errors)
                                / len(evaluation_errors),
                                2,
                            )
                            if evaluation_errors
                            else None
                        ),
                        "records": evaluation_errors,
                    },
                }
                store.predictions[analysis_id] = final_predictions
                store.zone_results[analysis_id] = final_statistics
                store.save_results(
                    analysis_id,
                    final_statistics,
                    graph,
                    final_predictions,
                    trajectories,
                )

                progress = min(99.0, (frame_index / max(frame_count, 1)) * 100.0)
                store.update_job(
                    analysis_id,
                    status=AnalysisStatus.PROCESSING,
                    progress_percent=progress,
                    processed_frames=processed,
                    current_frame=frame_index,
                    detected_count=len(tracks),
                    detected_frame_url=frame_url,
                    message=f"Processed frame {frame_index}; detected {len(tracks)} people",
                )
                broadcast_update(
                    analysis_id,
                    {
                        "status": "processing",
                        "progress_percent": progress,
                        "processed_frames": processed,
                        "detected_count": len(tracks),
                        "detected_frame_url": frame_url,
                        "zone_statistics": final_statistics,
                        "predictions": final_predictions,
                    },
                )

            frame_index += 1

        capture.release()

        if not final_statistics:
            raise RuntimeError(
                "No processable frames were found in the uploaded video"
            )

        if final_predictions:
            final_predictions["evaluation"]["status"] = (
                "completed_with_observations"
                if evaluation_errors
                else "insufficient_observation_horizon"
            )
            final_predictions["pending_forecast_count"] = len(pending_forecasts)
            store.predictions[analysis_id] = final_predictions

        store.update_job(
            analysis_id,
            status=AnalysisStatus.COMPLETED,
            progress_percent=100.0,
            processed_frames=processed,
            current_frame=frame_index,
            detected_count=len(current_ids) if "current_ids" in locals() else 0,
            detected_frame_url=(
                f"/storage/detected/{analysis_id}.jpg"
                if latest_frame_path
                else None
            ),
            message="Analysis completed",
        )
        broadcast_update(
            analysis_id,
            {
                "status": "completed",
                "progress_percent": 100.0,
                "processed_frames": processed,
                "zone_statistics": final_statistics,
                "predictions": final_predictions,
            },
        )
    except Exception as exc:
        try:
            capture.release()
        except Exception:
            pass
        store.update_job(
            analysis_id,
            status=AnalysisStatus.FAILED,
            progress_percent=100.0,
            error=str(exc),
            message="Analysis failed",
        )
        broadcast_update(
            analysis_id,
            {"status": "failed", "progress_percent": 100.0, "error": str(exc)},
        )
