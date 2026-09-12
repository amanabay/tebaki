"""tebaki CLI: validate and run."""

from __future__ import annotations

import argparse
import json
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

    summary = run_nightly_cycle(
        city_pack_name=args.city, auto_approve=(not args.no_auto_approve) if args.no_auto_approve is not None else None
    )
    _print_summary(summary)
    return 0


def _cmd_demo(args: argparse.Namespace) -> int:
    """Run a cycle that pauses for decisions, then resolve every card."""
    from app.orchestrator import resolve_decision, run_nightly_cycle
    from app.store import Report, get_store

    if args.seed:
        store = get_store()
        store.add_report(Report(category="waste", lat=9.010, lon=38.760, note="garbage pile on sidewalk"))
        store.add_report(Report(category="waste", lat=9.012, lon=38.758, note="trash not collected for days"))
        # Keep every seeded point inside the sandbox boundary so the same
        # scenario works through the API geo-fence and direct CLI execution.
        store.add_report(Report(category="pothole", lat=9.040, lon=38.790, note="deep pothole, hazard for motorcycles"))

    run_nightly_cycle(city_pack_name=args.city, auto_approve=False)
    store = get_store()
    cards = store.pending_cards()
    if not cards:
        print("no pending decision cards")
        return 0
    print(f"{len(cards)} decision card(s) pending; resolving with '{args.decision}'\n")
    for card in cards:
        fields = json.loads(args.fields) if args.decision == "edit" and args.fields else None
        outcome = resolve_decision(card.card_id, args.decision, fields)
        print(
            f"  {card.card_id} -> {outcome['action']}: complaint {outcome['complaint_id']} "
            f"is {outcome['status']}"
            + (f" (ticket {outcome['ticket_id']})" if outcome["ticket_id"] else "")
        )
    return 0


def _cmd_chase(args: argparse.Namespace) -> int:
    """Chase filed complaints: check tickets, evaluate SLA clocks, escalate stale cases."""
    from app.orchestrator import run_chase

    summary = run_chase(city_pack_name=args.city)
    _print_summary(summary)
    return 0


def _cmd_test_chicago(args: argparse.Namespace) -> int:
    """Check the Chicago Open311 channel: endpoint reachability, service codes, key.

    --file attempts one real filing (a genuine service request to Chicago 311).
    """
    import json as _json
    import os as _os
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parents[1] / "engine"))
    import httpx

    from app.city_pack import load_city_pack
    from app.config import settings as _settings

    pack = load_city_pack(_settings.cities_dir.resolve(), "chicago")
    api = pack.channels.api
    if api is None or api.type != "open311":
        print("[FAIL] chicago pack has no open311 channel")
        return 1

    base = api.endpoint.rstrip("/").removesuffix("/requests.json")
    services_url = f"{base}/services.json"
    params = {"jurisdiction_id": api.jurisdiction_id} if api.jurisdiction_id else None

    print(f"[1/3] fetching live services: {services_url}")
    try:
        resp = httpx.get(services_url, params=params, timeout=20)
        resp.raise_for_status()
        services = resp.json()
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] endpoint unreachable: {e}")
        return 1
    print(f"      {len(services)} services listed")

    print("[2/3] verifying service codes in the chicago pack")
    by_code = {s.get("service_code"): s.get("service_name") for s in services}
    code_map = api.service_code_map or {}
    ok = True
    for category, code in code_map.items():
        name = by_code.get(code)
        if name:
            print(f"      [OK] {category} -> {code} ({name})")
        else:
            print(f"      [FAIL] {category} -> {code} not in live services list")
            ok = False
    if not ok:
        return 1

    key = _os.getenv(api.api_key_env or "") if api.api_key_env else None
    print("[3/3] API key")
    if key:
        print(f"      key present via {api.api_key_env} ({key[:6]}…{key[-4:]})")
    else:
        print(f"      [WARN] {api.api_key_env} not set — production filings will be rejected")

    if not args.file:
        print("\nchannel reachable and codes verified. Authorization can only be proven by a")
        print("real filing — re-run with --file to submit one genuine service request.")
        return 0

    print("\n[--file] submitting one real service request (pothole, Monroe St)")
    from app.channels import Open311Channel

    channel = Open311Channel(
        endpoint=api.endpoint,
        jurisdiction_id=api.jurisdiction_id,
        api_key=key,
        service_code_map=code_map,
    )
    result = channel.file(
        {
            "category": "pothole",
            "lat": 41.8807,
            "lon": -87.6253,
            "subject": "Pothole on Monroe St",
            "text": (
                "Pothole forming in the right lane of Monroe St near the intersection with "
                "Wabash Ave; a hazard for cyclists. Requesting inspection and repair."
            ),
        }
    )
    if result.ok:
        print(f"      [OK] FILED — ticket/token {result.ticket_id}")
        print(_json.dumps({"ticket_id": result.ticket_id, "channel": result.channel}))
        return 0
    print(f"      [FAIL] filing rejected: {result.detail}")
    if "403" in result.detail or "401" in result.detail:
        print("      (key may still be pending city authorization — retry later)")
    return 1


def _print_summary(summary: dict) -> None:
    print(
        f"run {summary['run_id']} ({summary['city']}): "
        f"{len(summary['events'])} events, ended {summary['finished_at']}"
    )
    for event in summary["events"]:
        kind = event["kind"]
        rest = {k: v for k, v in event.items() if k not in ("at", "kind")}
        print(f"  {kind:<22} {rest}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="tebaki", description="Tebaki — the city's guardian")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate city pack YAML files")
    validate.add_argument("packs", nargs="*", help="pack files (default: cities/*.yaml)")
    validate.add_argument("--strict", action="store_true", help="also flag TODOs, placeholder emails, missing docs")
    validate.set_defaults(func=_cmd_validate)

    run = sub.add_parser("run", help="run the nightly cycle for a city pack")
    run.add_argument("--city", default="addis", help="city pack name (default: addis)")
    run.add_argument(
        "--no-auto-approve",
        action="store_true",
        help="pause on decision cards instead of sandbox auto-approve",
    )
    run.set_defaults(func=_cmd_run)

    demo = sub.add_parser("demo", help="run a cycle, then resolve all pending decision cards")
    demo.add_argument("--city", default="sandbox", help="city pack name (default: sandbox)")
    demo.add_argument("--decision", default="approve", choices=["approve", "edit", "drop"])
    demo.add_argument("--fields", help="JSON fields to merge when --decision edit")
    demo.add_argument("--seed", action="store_true", help="seed 3 sample reports first (self-contained demo)")
    demo.set_defaults(func=_cmd_demo)

    chase = sub.add_parser("chase", help="check filed tickets, escalate past-SLA complaints")
    chase.add_argument("--city", default="addis", help="city pack name (default: addis)")
    chase.set_defaults(func=_cmd_chase)

    test_chicago = sub.add_parser(
        "test-chicago", help="verify the Chicago Open311 channel (endpoint, codes, key)"
    )
    test_chicago.add_argument(
        "--file",
        action="store_true",
        help="also submit one REAL service request to Chicago 311",
    )
    test_chicago.set_defaults(func=_cmd_test_chicago)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
