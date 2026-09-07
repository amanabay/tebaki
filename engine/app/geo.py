"""Geospatial clustering and ward mapping.

- cluster_reports: H3 binning + DBSCAN density clustering over report
  coordinates (same category only), emitting hotspot clusters.
- map_ward: point-in-polygon lookup against the city pack boundary
  GeoJSON to resolve the admin unit (sub-city/community area).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import h3
from sklearn.cluster import DBSCAN

# H3 resolution 8 cells are ~174m edge-to-center in equatorial regions:
# fine-grained enough to separate streets, coarse enough to merge corners.
_H3_RES = 8

# DBSCAN over (lat, lon) degrees; ~330m radius (same-block/cross-street reports
# of one issue), min 1 report per cluster.
_DBSCAN_EPS_DEG = 0.003
_DBSCAN_MIN_SAMPLES = 1


@dataclass
class GeoPoint:
    lat: float
    lon: float
    category: str
    report_id: str
    note: str = ""
    severity: int = 3
    h3_cell: str = field(default="")
    plus_ones: int = 0


@dataclass
class Cluster:
    cluster_id: str
    category: str
    lat: float
    lon: float
    report_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    max_severity: int = 1
    h3_cells: list[str] = field(default_factory=list)
    ward: str = ""
    plus_ones: int = 0

    @property
    def residents(self) -> int:
        """Total residents backing the case: reporters + neighbor +1s."""
        return len(self.report_ids) + self.plus_ones


def cluster_reports(points: list[GeoPoint]) -> list[Cluster]:
    """Cluster points by category with H3 dedup + DBSCAN density grouping."""
    clusters: list[Cluster] = []
    categories = {p.category for p in points}
    for category in sorted(categories):
        cat_points = [p for p in points if p.category == category]
        for p in cat_points:
            p.h3_cell = h3.latlng_to_cell(p.lat, p.lon, _H3_RES)
        if len(cat_points) == 1:
            p = cat_points[0]
            clusters.append(_single_cluster(p))
            continue
        coords = [[p.lat, p.lon] for p in cat_points]
        labels = DBSCAN(eps=_DBSCAN_EPS_DEG, min_samples=_DBSCAN_MIN_SAMPLES).fit_predict(coords)
        for label in sorted(set(labels)):
            members = [p for p, l in zip(cat_points, labels, strict=True) if l == label]
            if len(members) == 1:
                clusters.append(_single_cluster(members[0]))
                continue
            clusters.append(
                Cluster(
                    cluster_id=f"CL-{h3.latlng_to_cell(members[0].lat, members[0].lon, _H3_RES)[:8].upper()}",
                    category=category,
                    lat=sum(m.lat for m in members) / len(members),
                    lon=sum(m.lon for m in members) / len(members),
                    report_ids=[m.report_id for m in members],
                    notes=[f"{m.report_id}: {m.note}" for m in members],
                    max_severity=max(m.severity for m in members),
                    h3_cells=sorted({m.h3_cell for m in members}),
                    plus_ones=sum(m.plus_ones for m in members),
                )
            )
    return clusters


def _single_cluster(p: GeoPoint) -> Cluster:
    return Cluster(
        cluster_id=f"CL-{p.h3_cell[:8].upper()}",
        category=p.category,
        lat=p.lat,
        lon=p.lon,
        report_ids=[p.report_id],
        notes=[f"{p.report_id}: {p.note}"],
        max_severity=p.severity,
        h3_cells=[p.h3_cell],
        plus_ones=p.plus_ones,
    )


def load_boundary_features(geojson_path: Path) -> list[dict]:
    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"expected FeatureCollection in {geojson_path}")
    return [f for f in data["features"] if f.get("geometry", {}).get("type") == "Polygon"]


def _point_in_ring(lat: float, lon: float, ring: list[list[float]]) -> bool:
    """Ray casting; ring is a list of [lon, lat] per GeoJSON spec."""
    x, y = lon, lat
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def map_ward(lat: float, lon: float, features: list[dict], fallback: str) -> str:
    """Return the admin-unit name containing the point, else fallback."""
    for feature in features:
        if _point_in_ring(lat, lon, feature["geometry"]["coordinates"][0]):
            return feature.get("properties", {}).get("name", fallback)
    return fallback


def is_within_boundary(lat: float, lon: float, features: list[dict]) -> bool:
    """True if the point falls inside any boundary polygon feature."""
    return any(_point_in_ring(lat, lon, f["geometry"]["coordinates"][0]) for f in features)
