from backend.app.persistence import SQLitePersistence
from backend.app.schemas import AnalysisProgress, AnalysisStatus, VideoMetadata, ZoneDefinition
from datetime import datetime, timezone


def test_sqlite_persists_video_analysis_zones_and_results(tmp_path) -> None:
    database = tmp_path / "test.db"
    persistence = SQLitePersistence(database)

    video = VideoMetadata(
        video_id="video-1",
        filename="crowd.mp4",
        path=r"C:\test\crowd.mp4",
        size_bytes=100,
        fps=30.0,
        frame_count=300,
        width=1920,
        height=1080,
        duration_seconds=10.0,
    )
    job = AnalysisProgress(
        analysis_id="analysis-1",
        video_id="video-1",
        status=AnalysisStatus.COMPLETED,
        progress_percent=100.0,
        processed_frames=30,
        total_frames=30,
        detected_count=4,
        message="Analysis completed",
        updated_at=datetime.now(timezone.utc),
    )
    zones = [
        ZoneDefinition(
            zone_id="entrance",
            name="Entrance",
            polygon=[[0, 0], [100, 0], [100, 100], [0, 100]],
            capacity=100,
        )
    ]
    statistics = [{"zone_id": "entrance", "occupancy": 4, "capacity": 100}]
    graph = {"directed": True, "nodes": [], "edges": [], "bottlenecks": []}
    predictions = {"analysis_id": "analysis-1", "horizon_seconds": [10, 20, 30], "forecasts": []}

    persistence.save_video(video)
    persistence.save_analysis(job)
    persistence.save_zones("analysis-1", zones)
    persistence.save_results(
        "analysis-1",
        statistics,
        graph,
        predictions,
        {"1": [{"frame_index": 10, "elapsed_seconds": 1.0, "x": 20.0, "y": 30.0}]},
    )

    assert persistence.load_videos()["video-1"].filename == "crowd.mp4"
    assert persistence.load_analyses()["analysis-1"].status == AnalysisStatus.COMPLETED
    assert persistence.load_zones()["analysis-1"][0].zone_id == "entrance"
    loaded_statistics, loaded_graph, loaded_predictions, loaded_trajectories = persistence.load_results()
    assert loaded_statistics["analysis-1"] == statistics
    assert loaded_graph["analysis-1"] == graph
    assert loaded_predictions["analysis-1"] == predictions
    assert loaded_trajectories["analysis-1"]["1"][0]["frame_index"] == 10
