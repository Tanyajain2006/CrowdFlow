import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "CrowdFlow"}


def test_missing_analysis_status() -> None:
    response = client.get("/analysis/status")
    assert response.status_code in (404, 200)


def test_upload_rejects_unsupported_file() -> None:
    response = client.post(
        "/video/upload",
        files={"file": ("document.txt", b"not a video", "text/plain")},
    )
    assert response.status_code == 415


def test_upload_accepts_generated_video(tmp_path) -> None:
    video_path = tmp_path / "test.mp4"
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (160, 120),
    )
    assert writer.isOpened()
    for _ in range(5):
        writer.write(np.zeros((120, 160, 3), dtype=np.uint8))
    writer.release()

    with video_path.open("rb") as video_file:
        response = client.post(
            "/video/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
        )

    assert response.status_code == 200
    payload = response.json()["video"]
    assert payload["filename"] == "test.mp4"
    assert payload["frame_count"] == 5
