from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import OUTPUT_DIR
from .routers import analysis, health, predictions, video, websocket, zones

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="CrowdFlow API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(video.router)
app.include_router(analysis.router)
app.include_router(zones.router)
app.include_router(predictions.router)
app.include_router(websocket.router)

app.mount("/storage", StaticFiles(directory=str(OUTPUT_DIR)), name="storage")

