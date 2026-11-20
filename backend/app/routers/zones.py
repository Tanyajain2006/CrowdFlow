from fastapi import APIRouter, HTTPException

from ..schemas import ZoneDefinition, ZoneUpdateRequest, VenueGraphResponse
from ..state import store

router = APIRouter(prefix="/zones", tags=["zones"])


@router.get("/current")
def get_current_zones(analysis_id: str | None = None) -> dict:
    if analysis_id:
        zones = store.zones.get(analysis_id, [])
        results = store.zone_results.get(analysis_id, [])
    else:
        zones = []
        results = []
        if store.latest_job():
            latest_id = store.latest_job().analysis_id
            zones = store.zones.get(latest_id, [])
            results = store.zone_results.get(latest_id, [])
    return {
        "zones": zones,
        "statistics": results,
    }


@router.post("/configure")
def configure_zones(body: ZoneUpdateRequest, analysis_id: str | None = None) -> dict:
    if not analysis_id:
        latest = store.latest_job()
        if not latest:
            raise HTTPException(status_code=404, detail="Start an analysis before configuring zones")
        analysis_id = latest.analysis_id
    store.save_zones(analysis_id, body.zones)
    return {"zones": body.zones}
