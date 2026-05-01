#!/usr/bin/env python3
"""Regenerate scripts/_protocol_constants.py from
agent-readiness-insights-protocol.

The leaderboard scoring scripts pivot per-rule findings into pillar
rollups. Hardcoding the pillar names here is a drift surface — a
protocol change adds a 5th pillar, the scripts silently keep emitting
four, and the public site goes stale.

This script reads the canonical enums out of the installed
``agent_readiness_insights_protocol`` package (the same package the
scanner depends on) and writes a single constants module that the
scoring scripts import. CI runs this script and asserts
``git diff --exit-code`` on the generated file.

Usage:

    python scripts/regen_protocol_constants.py

Run it after bumping the ``agent-readiness-insights-protocol`` pin
(via the scanner's pin chain).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _load_protocol_enums() -> dict[str, tuple[str, ...]]:
    try:
        from agent_readiness_insights_protocol import (  # type: ignore
            MatchType, Pillar, Severity,
        )
        return {
            "PILLARS": tuple(p.value for p in Pillar),
            "SEVERITIES": tuple(s.value for s in Severity),
            "OSS_MATCH_TYPES": tuple(m.value for m in MatchType),
        }
    except ImportError:
        pass

    here = Path(__file__).resolve().parent
    sibling = (
        here.parent.parent
        / "agent-readiness-insights-protocol"
        / "schemas"
        / "rule.schema.json"
    )
    if not sibling.is_file():
        sys.exit(
            "Could not import agent_readiness_insights_protocol and no "
            f"sibling schema found at {sibling}. Either install the "
            "package or check out the protocol repo as a sibling."
        )
    schema = json.loads(sibling.read_text())
    defs = schema.get("$defs", {})
    pillars = tuple(defs.get("Pillar", {}).get("enum", []))
    severities = tuple(defs.get("Severity", {}).get("enum", []))
    oss_match_types: list[str] = []
    for body in defs.values():
        const = (body.get("properties", {}).get("type") or {}).get("const")
        if const and "Match" in body.get("title", "") and "Private" not in body.get("title", ""):
            oss_match_types.append(const)
    return {
        "PILLARS": pillars,
        "SEVERITIES": severities,
        "OSS_MATCH_TYPES": tuple(sorted(set(oss_match_types))),
    }


HEADER = '''"""Auto-generated from agent-readiness-insights-protocol. DO NOT EDIT.

Regenerate via ``python scripts/regen_protocol_constants.py`` whenever
you bump the protocol pin (transitively, via the scanner). CI asserts
``git diff --exit-code`` on this file so a protocol enum addition
without a coordinated bump here is a hard error.
"""
from __future__ import annotations

'''


def render(consts: dict[str, tuple[str, ...]]) -> str:
    body = "\n".join(
        f"{name}: tuple[str, ...] = {tuple(consts[name])!r}"
        for name in ("PILLARS", "SEVERITIES", "OSS_MATCH_TYPES")
    )
    footer = '\n\n__all__ = ["PILLARS", "SEVERITIES", "OSS_MATCH_TYPES"]\n'
    return HEADER + body + footer


def main() -> int:
    consts = _load_protocol_enums()
    out = Path(__file__).resolve().parent / "_protocol_constants.py"
    out.write_text(render(consts))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
