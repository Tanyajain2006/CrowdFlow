from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO


class PedestrianDetector:
    """Loads pretrained YOLO person detection and runs Ultralytics ByteTrack."""

    def __init__(
        self,
        model_name: str,
        confidence: float = 0.35,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.confidence = confidence
        self.device = device
        self.model: YOLO | None = None

    def load(self) -> None:
        if self.model is not None:
            return
        model_path = Path(self.model_name)
        if model_path.is_file():
            self.model = YOLO(str(model_path))
        else:
            self.model = YOLO(self.model_name)

    def process_frame(self, frame: np.ndarray) -> tuple[list[dict[str, Any]], np.ndarray]:
        """Detect and track people in one frame, returning reusable track records."""
        self.load()
        if self.model is None:
            raise RuntimeError("YOLO model is unavailable")

        results = self.model.track(
            source=frame,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )
        annotated = frame.copy()
        tracks: list[dict[str, Any]] = []
        if not results:
            return tracks, annotated

        result = results[0]
        boxes = result.boxes
        if boxes is None:
            return tracks, annotated

        ids = boxes.id
        for index, box in enumerate(boxes.xyxy.cpu().numpy()):
            track_id = int(ids[index].item()) if ids is not None and index < len(ids) else None
            if track_id is None:
                continue

            x1, y1, x2, y2 = [float(value) for value in box]
            confidence = (
                float(boxes.conf[index].item())
                if boxes.conf is not None
                else 0.0
            )
            center_x = (x1 + x2) / 2.0
            bottom_y = y2
            tracks.append(
                {
                    "track_id": track_id,
                    "x1": x1,
                    "y1": y1,
                    "x2": x2,
                    "y2": y2,
                    "confidence": confidence,
                    "representative_x": center_x,
                    "representative_y": bottom_y,
                }
            )
            cv2.rectangle(
                annotated,
                (int(x1), int(y1)),
                (int(x2), int(y2)),
                (0, 200, 255),
                2,
            )
            cv2.putText(
                annotated,
                f"ID {track_id}",
                (int(x1), max(20, int(y1) - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 200, 255),
                2,
            )
            cv2.circle(
                annotated,
                (int(center_x), int(bottom_y)),
                4,
                (255, 255, 255),
                -1,
            )

        return tracks, annotated

