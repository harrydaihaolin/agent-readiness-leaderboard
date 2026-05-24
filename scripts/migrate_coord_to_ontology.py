"""One-shot migration: copy pillar_scores.coordination → pillar_scores.ontology
in every historical release JSON.

Run once during the M5 release window; thereafter, scanner emits both fields
natively via the M3.6 aggregator alias.

Idempotent: re-running on an already-migrated file is a no-op.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def migrate_file(path: Path) -> tuple[bool, str]:
    """Returns (modified, reason). Reason is empty when modified."""
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        # Some leaderboard releases are dicts of per-repo results; descend.
        modified = False
        for k, v in data.items():
            if isinstance(v, dict) and "pillar_scores" in v:
                modified |= _add_alias(v)
        if modified:
            path.write_text(json.dumps(data, indent=2))
        return modified, ""
    modified = False
    for entry in data:
        if isinstance(entry, dict):
            modified |= _add_alias(entry)
    if modified:
        path.write_text(json.dumps(data, indent=2))
    return modified, ""


def _add_alias(entry: dict) -> bool:
    ps = entry.get("pillar_scores")
    if not isinstance(ps, dict):
        return False
    if "coordination" in ps and "ontology" not in ps:
        ps["ontology"] = ps["coordination"]
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "data_dir",
        type=Path,
        nargs="?",
        default=Path(__file__).parent.parent / "data" / "releases",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    files = sorted(args.data_dir.glob("scores_v3_*.json"))
    if not files:
        files = sorted(args.data_dir.glob("*.json"))
    print(f"Found {len(files)} candidate files under {args.data_dir}")

    changed = 0
    for f in files:
        if args.dry_run:
            json.loads(f.read_text())
            print(f"  would scan {f.name}")
            continue
        modified, _ = migrate_file(f)
        if modified:
            print(f"  migrated {f.name}")
            changed += 1
    print(f"Total files modified: {changed}")


if __name__ == "__main__":
    main()
