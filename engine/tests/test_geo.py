"""Geo module tests: H3+DBSCAN clustering and ward mapping."""

from __future__ import annotations

from pathlib import Path

from app.geo import GeoPoint, cluster_reports, load_boundary_features, map_ward

CITIES_DIR = Path(__file__).parents[2] / "cities"


def test_nearby_same_category_merge_into_one_cluster() -> None:
    points = [
        GeoPoint(lat=9.010, lon=38.760, category="waste", report_id="R1", note="a", severity=3),
        GeoPoint(lat=9.012, lon=38.758, category="waste", report_id="R2", note="b", severity=5),
        GeoPoint(lat=9.100, lon=38.700, category="pothole", report_id="R3", note="c", severity=4),
    ]
    clusters = cluster_reports(points)
    assert len(clusters) == 2
    waste = next(c for c in clusters if c.category == "waste")
    assert set(waste.report_ids) == {"R1", "R2"}
    assert waste.max_severity == 5
    assert 9.005 < waste.lat < 9.017  # centroid between the two
    pothole = next(c for c in clusters if c.category == "pothole")
    assert pothole.report_ids == ["R3"]


def test_different_categories_never_merge() -> None:
    points = [
        GeoPoint(lat=9.010, lon=38.760, category="waste", report_id="R1"),
        GeoPoint(lat=9.0105, lon=38.7605, category="drain", report_id="R2"),
    ]
    clusters = cluster_reports(points)
    assert len(clusters) == 2
    assert {c.category for c in clusters} == {"waste", "drain"}


def test_distant_same_category_stay_separate() -> None:
    points = [
        GeoPoint(lat=9.010, lon=38.760, category="waste", report_id="R1"),
        GeoPoint(lat=9.050, lon=38.800, category="waste", report_id="R2"),
    ]
    clusters = cluster_reports(points)
    assert len(clusters) == 2


def test_h3_cells_populated() -> None:
    points = [GeoPoint(lat=9.010, lon=38.760, category="waste", report_id="R1")]
    (cluster,) = cluster_reports(points)
    assert cluster.h3_cells and cluster.h3_cells[0].isalnum()


def test_ward_mapping_inside_and_outside() -> None:
    features = load_boundary_features(CITIES_DIR / "geojson/sandbox.geojson")
    inside = map_ward(9.00, 38.75, features, fallback="nowhere")
    outside = map_ward(10.5, 39.5, features, fallback="nowhere")
    assert inside == "Sandbox District"
    assert outside == "nowhere"
