from pathlib import Path
from uuid import uuid4

import cv2
from fastapi import APIRouter, File, HTTPException, UploadFile

from ..config import (
    ALLOWED_VIDEO_CONTENT_TYPES,
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_UPLOAD_MB,
    VIDEO_DIR,
)
from ..schemas import VideoMetadata, VideoUploadResponse
from ..state import store

router = APIRouter(prefix="/video", tags=["video"])
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)) -> VideoUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="A video filename is required")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported video type '{suffix}'. Allowed: {', '.join(sorted(ALLOWED_VIDEO_EXTENSIONS))}",
        )
    if file.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media content type '{file.content_type}'",
        )

    destination = VIDEO_DIR / f"{uuid4().hex}{suffix}"
    size_bytes = 0
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024

    try:
        with destination.open("xb") as output:
            while chunk := await file.read(1024 * 1024):
                size_bytes += len(chunk)
                if size_bytes > max_bytes:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Video exceeds the {MAX_UPLOAD_MB} MB upload limit",
                    )
                output.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Could not save uploaded video: {exc}") from exc

    metadata = store.create_video(destination, Path(file.filename).name, size_bytes)
    capture = cv2.VideoCapture(str(destination))
    if not capture.isOpened():
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded file could not be opened as a video")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()

    metadata = store.update_video(
        metadata.video_id,
        fps=fps if fps > 0 else None,
        frame_count=frame_count if frame_count > 0 else None,
        width=width if width > 0 else None,
        height=height if height > 0 else None,
        duration_seconds=(frame_count / fps) if fps > 0 and frame_count > 0 else None,
    )
    return VideoUploadResponse(video=metadata)
