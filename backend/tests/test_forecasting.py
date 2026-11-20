from datetime import datetime, timezone

from backend.app.services.forecasting import calculate_forecasts, rolling_net_flow, risk_for


def test_positive_net_flow_predicts_capacity() -> None:
    net_flow = rolling_net_flow([
        (0.0, 2, 0),
        (1.0, 3, 0),
        (2.0, 4, 0),
    ])
    assert net_flow > 0
    assert risk_for(0.95) == "High"
    assert risk_for(1.2) == "Critical"


def test_forecast_returns_ten_twenty_and_thirty_seconds() -> None:
    statistics = [{
        "zone_id": "entrance",
        "occupancy": 8,
        "capacity": 20,
        "inflow": 2,
        "outflow": 1,
        "net_flow": 1.0,
    }]
    result = calculate_forecasts(
        statistics,
        {"entrance": [(0.0, 6), (1.0, 7), (2.0, 8)]},
        {"entrance": [(0.0, 2, 0), (1.0, 3, 1), (2.0, 4, 1)]},
        datetime.now(timezone.utc),
        0.8,
        {},
    )

    assert result["horizon_seconds"] == [10, 20, 30]
    assert len(result["forecasts"]) == 3
    assert all(item["observed_occupancy"] == 8 for item in result["forecasts"])
