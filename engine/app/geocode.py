"""Reverse geocoding: coordinates -> human-readable place names for complaints.

Uses the free Nominatim endpoint (OSM). Cached in-process; failures fall
back to None so callers degrade to coordinates. Disable entirely with
TEBAKI_GEOCODE=off (offline dev, CI).
"""

from __future__ import annotations

import os
import threading
from collections import OrderedDict
from typing import Any

import httpx

_NOMINATIM = "https://nominatim.openstreetmap.org/reverse"
_USER_AGENT = "Tebaki/0.1 (civic issue guardian; contact: tebakiapp@gmail.com)"
_TIMEOUT = 8.0
_CACHE_MAX = 512


class _LruCache:
    def __init__(self, max_entries: int = _CACHE_MAX) -> None:
        self._max = max_entries
        self._data: OrderedDict[tuple[float, float], str | None] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: tuple[float, float]) -> str | None | _Missing:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                return self._data[key]
        return _MISSING_SENTINEL

    def put(self, key: tuple[float, float], value: str | None) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self._max:
                self._data.popitem(last=False)


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover
        return "<missing>"


_MISSING_SENTINEL = _Missing()
_cache = _LruCache()


def geocode_enabled() -> bool:
    return os.getenv("TEBAKI_GEOCODE", "on").strip().lower() not in {"off", "0", "false", "no"}


def _round_key(lat: float, lon: float) -> tuple[float, float]:
    """~1.1km grid — plenty precise for place names, maximizes cache hits."""
    return (round(lat, 2), round(lon, 2))


def _format_place(data: dict[str, Any]) -> str | None:
    addr = data.get("address", {}) or {}
    # prefer the finest useful landmark pieces, OSM suburb/neighbourhood level
    for key in ("neighbourhood", "suburb", "quarter", "city_district", "village", "town"):
        if addr.get(key):
            place = addr[key]
            city = addr.get("city") or addr.get("town") or addr.get("municipality")
            return f"{place}, {city}" if city and city != place else place
    name = data.get("name") or data.get("display_name")
    if isinstance(name, str) and name:
        return name.split(",")[0].strip() or None
    return None


def reverse_geocode(lat: float, lon: float) -> str | None:
    """Resolve a human-readable place for the coordinates, or None.

    Never raises: network/parse failures degrade to None (callers fall
    back to coordinates).
    """
    if not geocode_enabled():
        return None
    key = _round_key(lat, lon)
    cached = _cache.get(key)
    if not isinstance(cached, _Missing):
        return cached
    try:
        resp = httpx.get(
            _NOMINATIM,
            params={"format": "jsonv2", "lat": lat, "lon": lon, "zoom": 16},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        place = _format_place(resp.json())
    except Exception:  # noqa: BLE001 — place names are best-effort
        place = None
    _cache.put(key, place)
    return place


def forward_geocode(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search places by name -> [{name, lat, lon}] for the report map.

    Never raises; failures degrade to an empty list.
    """
    if not geocode_enabled() or not query.strip():
        return []
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"format": "jsonv2", "q": query.strip(), "limit": limit},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return [
            {"name": r.get("display_name", ""), "lat": float(r["lat"]), "lon": float(r["lon"])}
            for r in resp.json()
            if r.get("lat") and r.get("lon")
        ]
    except Exception:  # noqa: BLE001
        return []
