from datetime import datetime, timedelta, timezone
from typing import Iterable


def rolling_net_flow(flow_history: Iterable[tuple[float, int, int]], window: int = 5) -> float:
    recent = list(flow_history)[-window:]
    if not recent:
        return 0.0
    seconds = max(recent[-1][0] - recent[0][0], 0.001)
    net = sum(inflow - outflow for _, inflow, outflow in recent)
    return net / max(seconds, 0.001)


def occupancy_trend(occupancy_history: Iterable[tuple[float, int]], window: int = 8) -> float:
    recent = list(occupancy_history)[-window:]
    if len(recent) < 2:
        return 0.0
    first_time, first_value = recent[0]
    last_time, last_value = recent[-1]
    elapsed = max(last_time - first_time, 0.001)
    return (last_value - first_value) / elapsed


def risk_for(utilization: float) -> str:
    if utilization >= 1.0:
        return "Critical"
    if utilization >= 0.85:
        return "High"
    if utilization >= 0.70:
        return "Moderate"
    return "Low"


def calculate_forecasts(
    zone_statistics: list[dict],
    zone_history: dict[str, object],
    flow_history: dict[str, object],
    generated_at: datetime,
    data_quality_score: float,
    affected_by: dict[str, list[str]],
) -> dict:
    forecasts: list[dict] = []
    for zone in zone_statistics:
        zone_id = zone["zone_id"]
        occupied_history = zone_history.get(zone_id, [])
        flows = flow_history.get(zone_id, [])
        net_per_second = rolling_net_flow(flows)
        trend_per_second = occupancy_trend(occupied_history)
        changed_flow = (net_per_second + trend_per_second) / 2.0
        capacity = zone["capacity"]
        observed = zone["occupancy"]

        time_to_capacity = None
        if changed_flow > 0:
            time_to_capacity = max(0.0, (capacity - observed) / changed_flow)
            if time_to_capacity > 24 * 60 * 60:
                time_to_capacity = None

        propagation = affected_by.get(zone_id, [])
        for horizon in (10, 20, 30):
            propagation_factor = 0.15 * len(propagation) if propagation else 0.0
            predicted = observed + (changed_flow * horizon)
            if propagation_factor:
                predicted += predicted * propagation_factor
            predicted = max(0.0, predicted)
            predicted = round(predicted, 2)
            forecast_utilization = predicted / capacity
            risk = risk_for(forecast_utilization)
            if time_to_capacity is not None and time_to_capacity <= horizon:
                risk = "Critical"

            reliability = "Low"
            if data_quality_score >= 0.75:
                reliability = "High"
            elif data_quality_score >= 0.45:
                reliability = "Moderate"

            assumptions = [
                "Net inflow and occupancy trend are treated as persons per second.",
                "Forecast uses the most recent rolling observations and assumes recent conditions persist.",
                "Forecast timestamps refer to elapsed video time.",
            ]
            if propagation:
                assumptions.append("The forecast includes limited propagation from congested neighboring zones.")

            forecasts.append(
                {
                    "zone_id": zone_id,
                    "observed_occupancy": observed,
                    "horizon_seconds": horizon,
                    "forecast_timestamp": (generated_at + timedelta(seconds=horizon)).isoformat(),
                    "predicted_occupancy": predicted,
                    "time_to_capacity_seconds": (
                        round(time_to_capacity, 2) if time_to_capacity is not None else None
                    ),
                    "risk": risk,
                    "assumptions": assumptions,
                    "reliability": reliability,
                    "data_quality_score": round(data_quality_score, 3),
                    "propagation_from": propagation,
                }
            )

    return {
        "horizon_seconds": [10, 20, 30],
        "forecasts": forecasts,
    }
