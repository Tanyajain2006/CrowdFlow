from fastapi import APIRouter, HTTPException

from ..state import store

router = APIRouter(tags=["predictions"])


@router.get("/predictions")
def get_predictions(analysis_id: str | None = None) -> dict:
    if analysis_id:
        result = store.predictions.get(analysis_id)
    else:
        latest = store.latest_job()
        result = store.predictions.get(latest.analysis_id) if latest else None
    if not result:
        raise HTTPException(status_code=404, detail="Predictions are not available")
    return result


@router.get("/graph")
def get_graph(analysis_id: str | None = None) -> dict:
    if analysis_id:
        result = store.graph_results.get(analysis_id)
    else:
        latest = store.latest_job()
        result = store.graph_results.get(latest.analysis_id) if latest else None
    if not result:
        raise HTTPException(status_code=404, detail="Venue graph is not available")
    return result
