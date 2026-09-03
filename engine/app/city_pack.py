"""City Pack loading and validation."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.models.city_pack import CityPack

_PACK_NAME_RE = re.compile(r"^[a-z0-9-]+$")
_TODO_RE = re.compile(r"TODO", re.IGNORECASE)


class CityPackError(Exception):
    """Raised when a city pack cannot be loaded (fatal problems only)."""


def load_city_pack(cities_dir: Path, name: str) -> CityPack:
    if not _PACK_NAME_RE.match(name):
        raise CityPackError(f"invalid pack name {name!r}: must be lowercase letters/digits/hyphens")
    path = cities_dir / f"{name}.yaml"
    if not path.is_file():
        available = sorted(p.stem for p in cities_dir.glob("*.yaml"))
        raise CityPackError(f"city pack not found: {path} (available: {available})")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise CityPackError(f"invalid YAML in {path}: {e}") from e
    try:
        pack = CityPack.model_validate(data)
    except ValidationError as e:
        raise CityPackError(f"invalid city pack {path}:\n{_format_validation_error(e)}") from e
    geojson_path = cities_dir / pack.boundary.geojson
    if not geojson_path.is_file():
        raise CityPackError(f"boundary geojson not found: {geojson_path}")
    return pack


def validate_pack_file(path: Path, strict: bool = False) -> list[str]:
    """Return human-readable problems with a pack. Empty list means valid.

    strict=True additionally flags unresolved TODO-RESEARCH placeholders,
    missing regulation docs, and placeholder email addresses.
    """
    issues: list[str] = []
    cities_dir = path.parent
    try:
        load_city_pack(cities_dir, path.stem)
    except CityPackError as e:
        issues.append(str(e))
        return issues
    pack = load_city_pack(cities_dir, path.stem)

    if strict:
        issues.extend(_strict_issues(pack, path, cities_dir))
    return issues


def _strict_issues(pack: CityPack, path: Path, cities_dir: Path) -> list[str]:
    issues: list[str] = []
    raw = path.read_text(encoding="utf-8")
    if _TODO_RE.search(raw):
        issues.append(f"{path.name}: contains TODO markers (research pending)")
    if pack.boundary.note and _TODO_RE.search(pack.boundary.note):
        issues.append(f"{path.name}: boundary is a placeholder — replace with OSM extract")
    for reg in pack.regulations:
        if reg.doc:
            doc_path = cities_dir / reg.doc
            if not doc_path.is_file():
                issues.append(f"{path.name}: regulation doc missing: {doc_path}")
    for channel in pack.channels.email:
        if channel.address.endswith("@placeholder.invalid"):
            issues.append(f"{path.name}: placeholder email for {channel.target!r}")
    if _TODO_RE.search(pack.pitch.number) or _TODO_RE.search(pack.pitch.source):
        issues.append(f"{path.name}: pitch number/source is a TODO placeholder")
    return issues


def _format_validation_error(e: ValidationError) -> str:
    lines = []
    for err in e.errors():
        loc = ".".join(str(part) for part in err["loc"])
        lines.append(f"  {loc or '<root>'}: {err['msg']}")
    return "\n".join(lines)
