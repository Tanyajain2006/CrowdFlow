from backend.app.schemas import ZoneDefinition
from backend.app.services.zone_analytics import ZoneAnalytics, point_in_polygon


def test_point_inside_polygon() -> None:
    polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
    assert point_in_polygon(50, 50, polygon)
    assert not point_in_polygon(150, 50, polygon)


def test_zone_occupancy_counts_track_once() -> None:
    zone = ZoneDefinition(
        zone_id="entrance",
        name="Entrance",
        polygon=[[0, 0], [100, 0], [100, 100], [0, 100]],
        capacity=50,
    )
    analytics = ZoneAnalytics([zone])
    tracks = [
        {"track_id": 1, "representative_x": 20, "representative_y": 20},
        {"track_id": 1, "representative_x": 21, "representative_y": 21},
    ]

    statistics = analytics.update(tracks, 1.0)

    assert statistics[0]["occupancy"] == 1
    assert statistics[0]["inflow"] == 1
