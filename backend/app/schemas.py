from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VideoMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    video_id: str
    filename: str
    path: str
    size_bytes: int
    fps: float | None = None
    frame_count: int | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None


class VideoUploadResponse(BaseModel):
    video: VideoMetadata


class AnalysisStartRequest(BaseModel):
    video_id: str = Field(min_length=1)
    frame_interval: int = Field(default=10, ge=1, le=300)
    zones: list["ZoneDefinition"] | None = None


class AnalysisProgress(BaseModel):
    analysis_id: str
    video_id: str
    status: AnalysisStatus
    progress_percent: float = 0.0
    processed_frames: int = 0
    total_frames: int = 0
    current_frame: int | None = None
    message: str = ""
    error: str | None = None
    detected_count: int = 0
    detected_frame_url: str | None = None
    updated_at: datetime


class ZoneDefinition(BaseModel):
    zone_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    polygon: list[list[float]] = Field(min_length=3)
    capacity: int = Field(ge=1)
    area_sq_pixels: float | None = Field(default=None, gt=0)


class ZoneUpdateRequest(BaseModel):
    zones: list[ZoneDefinition] = Field(min_length=1)


class ZoneStatistics(BaseModel):
    zone_id: str
    name: str
    occupancy: int
    capacity: int
    utilization: float
    inflow: int
    outflow: int
    net_flow: float
    density_per_1000_sq_pixels: float
    average_speed_px_per_second: float


class GraphNode(BaseModel):
    id: str
    label: str
    capacity: int
    occupancy: int


class GraphEdge(BaseModel):
    source: str
    target: str
    capacity: int
    pathway_capacity: int


class ZoneEdgeDefinition(BaseModel):
    source: str
    target: str
    capacity: int = Field(default=100, ge=1)


class VenueGraphResponse(BaseModel):
    directed: bool = True
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    bottlenecks: list[str]


class PredictionRisk(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"


class ZoneForecast(BaseModel):
    zone_id: str
    observed_occupancy: int
    horizon_seconds: int
    forecast_timestamp: datetime
    predicted_occupancy: float
    time_to_capacity_seconds: float | None
    risk: PredictionRisk
    assumptions: list[str]
    reliability: Literal["Low", "Moderate", "High"]
    data_quality_score: float
    propagation_from: list[str] = []


class PredictionResponse(BaseModel):
    analysis_id: str
    horizon_seconds: list[int]
    generated_at: datetime
    forecasts: list[ZoneForecast]
    evaluation: dict[str, Any] = {}


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str = "CrowdFlow"

