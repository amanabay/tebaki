"""tebaki CLI: validate and run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "engine"))

if __name__ == "__main__":
    sys.path.insert(0, str(REPO_ROOT / "sandbox-portal"))


def _cmd_validate(args: argparse.Namespace) -> int:
    from app.city_pack import validate_pack_file

    targets = [Path(p) for p in args.packs]
    if not targets:
        targets = sorted((REPO_ROOT / "cities").glob("*.yaml"))
    failures = 0
    for target in targets:
        issues = validate_pack_file(target, strict=args.strict)
        name = target.name
        if issues:
            failures += 1
            for issue in issues:
                print(f"[FAIL] {issue}")
        else:
            print(f"[OK] {name}")
    if failures:
        print(f"\n{failures} pack(s) with issues")
        return 1
    print("\nall packs valid" + (" (strict)" if args.strict else ""))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from app.orchestrator import run_nightly_cycle

    summary = run_nightly_cycle(city_pack_name=args.city)
    print(
        f"run {summary['run_id']} ({summary['city']}): "
        f"{len(summary['events'])} events, ended {summary['finished_at']}"
    )
    for event in summary["events"]:
        kind = event["kind"]
        rest = {k: v for k, v in event.items() if k not in ("at", "kind")}
        print(f"  {kind:<22} {rest}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="tebaki", description="Tebaki — the city's guardian")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate city pack YAML files")
    validate.add_argument("packs", nargs="*", help="pack files (default: cities/*.yaml)")
    validate.add_argument("--strict", action="store_true", help="also flag TODOs, placeholder emails, missing docs")
    validate.set_defaults(func=_cmd_validate)

    run = sub.add_parser("run", help="run the nightly cycle for a city pack")
    run.add_argument("--city", default="sandbox", help="city pack name (default: sandbox)")
    run.set_defaults(func=_cmd_run)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
