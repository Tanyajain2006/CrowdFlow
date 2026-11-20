from collections import defaultdict, deque
from typing import Iterable

import cv2

from ..schemas import ZoneDefinition


def point_in_polygon(x: float, y: float, polygon: Iterable[list[float]]) -> bool:
    import numpy as np

    point = np.array([[x, y]], dtype=np.float32)
    vertices = np.array(polygon, dtype=np.int32)
    return cv2.pointPolygonTest(vertices, tuple(point[0]), False) >= 0


def default_zones(width: int, height: int) -> list[ZoneDefinition]:
    w, h = float(width), float(height)
    return [
        ZoneDefinition(
            zone_id="main-stage",
            name="Main Stage",
            polygon=[[0.05 * w, 0.05 * h], [0.95 * w, 0.05 * h], [0.95 * w, 0.35 * h], [0.05 * w, 0.35 * h]],
            capacity=max(20, int(w * h * 0.00035)),
        ),
        ZoneDefinition(
            zone_id="corridor",
            name="Corridor",
            polygon=[[0.35 * w, 0.32 * h], [0.65 * w, 0.32 * h], [0.65 * w, 0.68 * h], [0.35 * w, 0.68 * h]],
            capacity=max(15, int(w * h * 0.00020)),
        ),
        ZoneDefinition(
            zone_id="entrance",
            name="Entrance",
            polygon=[[0.05 * w, 0.65 * h], [0.34 * w, 0.65 * h], [0.34 * w, 0.95 * h], [0.05 * w, 0.95 * h]],
            capacity=max(20, int(w * h * 0.00025)),
        ),
        ZoneDefinition(
            zone_id="food-court",
            name="Food Court",
            polygon=[[0.66 * w, 0.65 * h], [0.95 * w, 0.65 * h], [0.95 * w, 0.95 * h], [0.66 * w, 0.95 * h]],
            capacity=max(20, int(w * h * 0.00025)),
        ),
        ZoneDefinition(
            zone_id="exit",
            name="Exit",
            polygon=[[0.34 * w, 0.69 * h], [0.66 * w, 0.69 * h], [0.66 * w, 0.95 * h], [0.34 * w, 0.95 * h]],
            capacity=max(20, int(w * h * 0.00020)),
        ),
    ]


class ZoneAnalytics:
    def __init__(self, zones: list[ZoneDefinition]) -> None:
        self.zones = zones
        self.track_zone: dict[int, str | None] = {}
        self.track_positions: dict[int, deque[tuple[float, float, float]]] = defaultdict(
            lambda: deque(maxlen=30)
        )
        self.zone_occupancy_history: dict[str, deque[tuple[float, int]]] = defaultdict(
            lambda: deque(maxlen=60)
        )
        self.zone_flow_history: dict[str, deque[tuple[float, int, int]]] = defaultdict(
            lambda: deque(maxlen=60)
        )

    def map_zone(self, x: float, y: float) -> str | None:
        for zone in self.zones:
            if point_in_polygon(x, y, zone.polygon):
                return zone.zone_id
        return None

    def update(
        self,
        tracks: list[dict],
        elapsed_seconds: float,
    ) -> list[dict]:
        occupants: dict[str, set[int]] = {zone.zone_id: set() for zone in self.zones}
        inflow: dict[str, int] = {zone.zone_id: 0 for zone in self.zones}
        outflow: dict[str, int] = {zone.zone_id: 0 for zone in self.zones}
        visible_track_ids = {int(track["track_id"]) for track in tracks}

        for track in tracks:
            track_id = int(track["track_id"])
            x = float(track["representative_x"])
            y = float(track["representative_y"])
            new_zone = self.map_zone(x, y)
            if new_zone:
                occupants[new_zone].add(track_id)

            previous_zone = self.track_zone.get(track_id)
            if previous_zone != new_zone:
                if previous_zone and previous_zone in outflow:
                    outflow[previous_zone] += 1
                if new_zone and new_zone in inflow:
                    inflow[new_zone] += 1
            self.track_zone[track_id] = new_zone
            self.track_positions[track_id].append((elapsed_seconds, x, y))

        disappeared_ids = set(self.track_zone) - visible_track_ids
        for track_id in disappeared_ids:
            previous_zone = self.track_zone.get(track_id)
            if previous_zone and previous_zone in outflow:
                outflow[previous_zone] += 1
            self.track_zone.pop(track_id, None)

        statistics: list[dict] = []
        for zone in self.zones:
            zone_id = zone.zone_id
            occupancy = len(occupants[zone_id])
            zone_area = zone.area_sq_pixels
            if not zone_area:
                xs = [point[0] for point in zone.polygon]
                ys = [point[1] for point in zone.polygon]
                zone_area = max(1.0, (max(xs) - min(xs)) * (max(ys) - min(ys)))

            speed_samples: list[float] = []
            for track_id in occupants[zone_id]:
                positions = list(self.track_positions[track_id])
                if len(positions) >= 2:
                    recent = positions[-2:]
                    dt = max(recent[1][0] - recent[0][0], 0.001)
                    distance = ((recent[1][1] - recent[0][1]) ** 2 + (recent[1][2] - recent[0][2]) ** 2) ** 0.5
                    speed_samples.append(distance / dt)

            average_speed = sum(speed_samples) / len(speed_samples) if speed_samples else 0.0
            net_flow = float(inflow[zone_id] - outflow[zone_id])
            density = occupancy / (zone_area / 1000.0)

            self.zone_occupancy_history[zone_id].append((elapsed_seconds, occupancy))
            self.zone_flow_history[zone_id].append((elapsed_seconds, inflow[zone_id], outflow[zone_id]))
            statistics.append(
                {
                    "zone_id": zone_id,
                    "name": zone.name,
                    "occupancy": occupancy,
                    "capacity": zone.capacity,
                    "utilization": occupancy / zone.capacity,
                    "inflow": inflow[zone_id],
                    "outflow": outflow[zone_id],
                    "net_flow": net_flow,
                    "density_per_1000_sq_pixels": round(density, 4),
                    "average_speed_px_per_second": round(average_speed, 2),
                }
            )

        return statistics
