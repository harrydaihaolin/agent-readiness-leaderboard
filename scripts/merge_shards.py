#!/usr/bin/env python3
"""
Merge sharded scan envelopes back into a single canonical scores.json.

`scripts/scan.py --shard N/M` writes one shard at a time. This script
takes the M shard files, concatenates `repos[]` + `failures[]` into a
single envelope, recomputes `total_repos`, validates against
`schemas/scores.schema.json`, and writes the unified envelope.

Idempotent: re-running with the same shard files produces byte-stable
output (modulo `last_updated` which is taken from the *latest* shard).

Usage:
  python scripts/merge_shards.py \
      --shards data/releases/_shards/scores.shard1of4.json ... \
      --output data/releases/scores_v3_1000_2026-05-01.json \
      --scan-health data/releases/scan_health_v3.json

Exit codes:
  0 — merge OK and schema-valid
  1 — bad inputs (missing shards, mismatched M, schema invalid, ...)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "schemas" / "scores.schema.json"


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"shard file not found: {path}")
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SystemExit(f"shard file {path} is not valid JSON: {exc}") from exc


def _validate_shards(shards: list[dict[str, Any]]) -> tuple[int, str]:
    """Confirm the shard tuple is well-formed and complete.

    Returns ``(total_M, scan_mode)``. Raises ``SystemExit`` on drift.
    """
    if not shards:
        raise SystemExit("--shards must list at least one shard file")
    totals = {s.get("shard", {}).get("total") for s in shards}
    if None in totals:
        raise SystemExit(
            "one or more shard files missing 'shard.total'; "
            "did you forget --shard on scan.py?"
        )
    if len(totals) != 1:
        raise SystemExit(f"shards disagree on total: {totals}")
    total_m = totals.pop()
    if not isinstance(total_m, int) or total_m < 1:
        raise SystemExit(f"invalid shard.total: {total_m!r}")
    seen = sorted(s["shard"]["index"] for s in shards)
    expected = list(range(1, total_m + 1))
    if seen != expected:
        raise SystemExit(
            f"missing shards: have {seen}, expected {expected}"
        )
    modes = {s.get("scan_mode") for s in shards}
    if len(modes) != 1:
        raise SystemExit(f"shards disagree on scan_mode: {modes}")
    return total_m, modes.pop() or "unknown"


def _stitch(shards: list[dict[str, Any]], scan_mode: str) -> dict[str, Any]:
    repos: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    seen_repo_keys: set[str] = set()
    last_updated = max(s.get("last_updated", "") for s in shards)
    # Take scanner metadata from the first shard with non-null values.
    scanner_version = next(
        (s.get("scanner_version") for s in shards if s.get("scanner_version")),
        None,
    )
    rules_pack_version = next(
        (s.get("rules_pack_version") for s in shards if s.get("rules_pack_version")),
        None,
    )
    checks_count = next(
        (
            s.get("checks_count")
            for s in shards
            if isinstance(s.get("checks_count"), int)
        ),
        None,
    )
    for s in shards:
        for r in s.get("repos") or []:
            key = (r.get("repo") or "").lower()
            if key and key in seen_repo_keys:
                # The hash partition guarantees disjoint shards. If we
                # see a duplicate we'd rather red-line than silently
                # double-count.
                raise SystemExit(
                    f"duplicate repo across shards: {r.get('repo')!r}"
                )
            seen_repo_keys.add(key)
            repos.append(r)
        for f in s.get("failures") or []:
            failures.append(f)
    repos.sort(key=lambda x: x.get("overall_score", 0.0), reverse=True)
    for i, r in enumerate(repos, 1):
        r["rank"] = i
    return {
        "last_updated": last_updated,
        "scan_version": shards[0].get("scan_version", "2.1.0"),
        "scanner": shards[0].get("scanner", "agent-readiness"),
        "scanner_version": scanner_version,
        "rules_pack_version": rules_pack_version,
        "checks_count": checks_count,
        "total_repos": len(repos),
        "repos": repos,
        "failures": failures,
        "scan_mode": scan_mode,
    }


def _validate_against_schema(envelope: dict[str, Any]) -> None:
    """Optional belt-and-braces schema check using check-jsonschema.

    The release-v3-snapshot workflow re-runs check-jsonschema on the
    final file anyway; running it here too means a local merge fails
    fast instead of waiting for CI.
    """
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        # jsonschema is in the leaderboard's requirements but we don't
        # want to make merge_shards.py hard-depend on it for ad-hoc use.
        print(
            "warning: jsonschema not installed; skipping local schema check",
            file=sys.stderr,
        )
        return
    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(envelope), key=lambda e: e.path)
    if errors:
        first = errors[0]
        path = "/".join(str(p) for p in first.path) or "(root)"
        raise SystemExit(
            f"merged envelope failed schema check at {path}: {first.message}"
        )


def _rebuild_scan_health(
    envelope: dict[str, Any], path: Path, prior: dict[str, dict[str, Any]]
) -> None:
    """Rebuild scan_health from the merged envelope.

    See scan.py: per-shard runs intentionally skip writing this file.
    The merger reconstitutes it once it has the full picture.
    """
    rows: list[dict[str, Any]] = []
    scanned_at = envelope["last_updated"]
    successes = {r["repo"] for r in envelope["repos"]}
    failure_repos = {f["repo"] for f in envelope["failures"]}
    for repo in sorted(successes):
        prev = prior.get(repo, {})
        rows.append(
            {
                "repo": repo,
                "last_success_ts": scanned_at,
                "last_failure_ts": prev.get("last_failure_ts"),
                "consecutive_failures": 0,
                "error_class": None,
            }
        )
    for fail in envelope["failures"]:
        repo = fail["repo"]
        prev = prior.get(repo, {})
        prev_streak = prev.get("consecutive_failures") or 0
        streak = (
            1
            if prev.get("error_class") in (None, "")
            else int(prev_streak) + 1
        )
        rows.append(
            {
                "repo": repo,
                "last_success_ts": prev.get("last_success_ts"),
                "last_failure_ts": scanned_at,
                "consecutive_failures": streak,
                "error_class": fail["error_class"],
            }
        )
    rows.sort(key=lambda r: (-(r["consecutive_failures"] or 0), r["repo"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"last_updated": scanned_at, "repos": rows},
            indent=2,
        )
    )
    _ = failure_repos  # reserved for future drift checks


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--shards",
        nargs="+",
        type=Path,
        required=True,
        help="Two or more shard files written by scan.py --shard.",
    )
    ap.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Where to write the merged scores.json.",
    )
    ap.add_argument(
        "--scan-health",
        type=Path,
        default=None,
        help=(
            "If set, rewrite scan_health.json from the merged envelope. "
            "Pass --scan-health '' to skip."
        ),
    )
    ap.add_argument(
        "--no-schema-check",
        action="store_true",
        help="Skip the local jsonschema validation step.",
    )
    args = ap.parse_args()

    shards = [_load(p) for p in args.shards]
    total_m, scan_mode = _validate_shards(shards)
    print(
        f"Merging {len(shards)} shards (M={total_m}, scan_mode={scan_mode}) ..."
    )

    envelope = _stitch(shards, scan_mode)
    if not args.no_schema_check:
        _validate_against_schema(envelope)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(envelope, indent=2))
    print(
        f"Wrote {args.output}: {envelope['total_repos']} repos, "
        f"{len(envelope['failures'])} failures."
    )

    if args.scan_health:
        prior: dict[str, dict[str, Any]] = {}
        if args.scan_health.is_file():
            try:
                prior_doc = json.loads(args.scan_health.read_text())
                if isinstance(prior_doc, dict):
                    for row in prior_doc.get("repos") or []:
                        if isinstance(row, dict) and isinstance(
                            row.get("repo"), str
                        ):
                            prior[row["repo"]] = row
            except json.JSONDecodeError:
                pass
        _rebuild_scan_health(envelope, args.scan_health, prior)
        print(f"Wrote scan_health → {args.scan_health}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
