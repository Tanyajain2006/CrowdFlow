from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from ..schemas import AnalysisProgress, AnalysisStartRequest
from ..state import store

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/start", response_model=AnalysisProgress)
def start_analysis(body: AnalysisStartRequest, background_tasks: BackgroundTasks) -> AnalysisProgress:
    video_id = str(body.video_id)
    if not store.get_video(video_id):
        raise HTTPException(status_code=404, detail="Uploaded video was not found")

    job = store.create_job(video_id)
    if body.zones:
        store.save_zones(job.analysis_id, body.zones)

    from ..services.analysis_engine import run_analysis

    background_tasks.add_task(
        run_analysis,
        job.analysis_id,
        video_id,
        body.frame_interval,
    )
    return job


@router.get("/status", response_model=AnalysisProgress)
def get_status(analysis_id: str | None = Query(default=None)) -> AnalysisProgress:
    if analysis_id:
        job = store.get_job(analysis_id)
        if not job:
            raise HTTPException(status_code=404, detail="Analysis was not found")
        return job
    job = store.latest_job()
    if not job:
        raise HTTPException(status_code=404, detail="No analysis has been started")
    return job


@router.get("/frame/{analysis_id}")
def get_detected_frame(analysis_id: str) -> FileResponse:
    frame_path = store.detected_frames.get(analysis_id)
    if not frame_path:
        raise HTTPException(status_code=404, detail="No processed detection frame is available")
    return FileResponse(frame_path, media_type="image/jpeg")


@router.get("/trajectories/{analysis_id}")
def get_trajectories(analysis_id: str) -> dict:
    job = store.get_job(analysis_id)
    if not job:
        raise HTTPException(status_code=404, detail="Analysis was not found")
    trajectory_history = store.track_history.get(analysis_id, {})
    serialized = {
        str(track_id): points
        for track_id, points in trajectory_history.items()
    }
    return {
        "analysis_id": analysis_id,
        "track_count": len(serialized),
        "trajectories": serialized,
    }
