import networkx as nx

from ..schemas import ZoneDefinition


def build_venue_graph(
    zones: list[ZoneDefinition],
    statistics: list[dict],
    capacities: dict[str, int] | None = None,
) -> dict:
    graph = nx.DiGraph()
    occupancy_by_zone = {item["zone_id"]: item["occupancy"] for item in statistics}

    for zone in zones:
        graph.add_node(
            zone.zone_id,
            label=zone.name,
            capacity=zone.capacity,
            occupancy=occupancy_by_zone.get(zone.zone_id, 0),
        )

    names = {zone.name.lower(): zone.zone_id for zone in zones}
    zone_ids = {zone.zone_id for zone in zones}
    candidate_edges = [
        ("entrance", "corridor"),
        ("corridor", "main-stage"),
        ("main-stage", "exit"),
        ("corridor", "food-court"),
        ("food-court", "exit"),
        ("corridor", "exit"),
    ]

    candidate_edges = [
        (source, target)
        for source, target in candidate_edges
        if source in zone_ids and target in zone_ids
    ]
    for index, (source, target) in enumerate(candidate_edges):
        pathway_capacity = capacities.get(source, 100) if capacities else 100
        graph.add_edge(
            source,
            target,
            capacity=pathway_capacity,
            pathway_capacity=pathway_capacity,
            edge_id=f"pathway-{index}",
        )

    bottlenecks: list[str] = []
    affected: dict[str, list[str]] = {}
    for zone in zones:
        occupancy = occupancy_by_zone.get(zone.zone_id, 0)
        if zone.capacity > 0 and occupancy / zone.capacity >= 0.85:
            bottlenecks.append(zone.zone_id)

    for zone_id in bottlenecks:
        affected[zone_id] = [
            neighbor
            for neighbor in graph.successors(zone_id)
        ]

    nodes = [
        {
            "id": node,
            "label": data["label"],
            "capacity": data["capacity"],
            "occupancy": data["occupancy"],
        }
        for node, data in graph.nodes(data=True)
    ]
    edges = [
        {
            "source": source,
            "target": target,
            "capacity": data["capacity"],
            "pathway_capacity": data["pathway_capacity"],
        }
        for source, target, data in graph.edges(data=True)
    ]
    return {
        "directed": True,
        "nodes": nodes,
        "edges": edges,
        "bottlenecks": bottlenecks,
        "affected_zones": affected,
    }
