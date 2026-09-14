"""Geo module tests: H3+DBSCAN clustering and ward mapping."""

from __future__ import annotations

import json
from pathlib import Path

from app.geo import GeoPoint, cluster_reports, is_within_boundary, load_boundary_features, map_ward

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


def test_addis_bole_pilot_precedes_the_city_fallback() -> None:
    features = load_boundary_features(CITIES_DIR / "geojson/addis.geojson")
    assert map_ward(9.0, 38.80, features, fallback="outside") == "Bole"
    assert map_ward(9.0321, 38.7421, features, fallback="outside") == (
        "Addis Ababa city boundary (published administrative extent)"
    )
    assert is_within_boundary(9.0321, 38.7421, features)


def test_multipolygon_boundaries_are_loaded_and_mapped(tmp_path: Path) -> None:
    path = tmp_path / "multipart.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "Island Ward"},
                        "geometry": {
                            "type": "MultiPolygon",
                            "coordinates": [
                                [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                                [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    features = load_boundary_features(path)
    assert len(features) == 1
    assert map_ward(2.5, 2.5, features, fallback="outside") == "Island Ward"
    assert is_within_boundary(0.5, 0.5, features)
    assert not is_within_boundary(4, 4, features)
