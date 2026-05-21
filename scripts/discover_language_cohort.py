#!/usr/bin/env python3
"""Discover a language-stratified GitHub cohort.

The default ``discover_repos.py`` sweeps by *topic* (llm, agents, rag, …)
which biases the corpus heavily toward Python / TypeScript. The v3
1000-repo cohort produced by that script under-represents the language
populations the calibration cycle on 2026-05-21 actually wanted to
measure improvements against: zero Scala, 1 Clojure, 1 Julia, 6 Kotlin,
15 Java in 993 repos.

This script iterates a fixed list of ``language:`` qualifiers with star
bands so the resulting cohort skews toward JVM and "long tail" languages
(Scala, Clojure, Kotlin, Erlang, Elixir, OCaml, Julia, R, Haskell). The
cohort is frozen as a versioned JSON artefact alongside ``dataset_*.json``.

Inputs
------

* ``LANGUAGE_COHORT_LANGUAGES`` — comma-separated GitHub languages.
  Defaults to the "JVM-skewed" set below.
* ``LANGUAGE_COHORT_PER_LANG`` — max repos per language. Default 12.
* ``LANGUAGE_COHORT_MAX_RESULTS`` — global cap. Default 100.
* ``LANGUAGE_COHORT_STAR_BANDS`` — comma-separated star ranges. Default
  matches ``discover_repos.DEFAULT_STAR_BANDS``.
* ``LANGUAGE_COHORT_OUT`` — output path. Default
  ``data/cohorts/jvm_skewed_v1.json``.
* ``GITHUB_TOKEN`` — required to lift the search rate limit beyond
  10 req/min.

Outputs
-------

A JSON artefact with the same shape as ``discover_repos.py``:

```json
{
  "updated_at": "...",
  "cohort_name": "jvm_skewed_v1",
  "query": {"languages": [...], "per_language": 12, "star_bands": [...]},
  "max_results": 100,
  "repos": ["org/name", ...],
  "by_language": {"Scala": 18, "Clojure": 12, ...},
  "search_meta": [...]
}
```
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "cohorts"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from discover_repos import _accept_items, _search_paginated  # noqa: E402

DEFAULT_LANGUAGES = [
    "Scala",
    "Clojure",
    "Kotlin",
    "Java",
    "Erlang",
    "Elixir",
    "OCaml",
    "Julia",
    "R",
    "Haskell",
    "F#",
    "Groovy",
]

# Sweep highest stars first so the cohort skews toward production-grade
# repos rather than experimental playgrounds in the lowest band. The
# per-language cap is hit before we descend to the long tail.
DEFAULT_STAR_BANDS = [
    "10001..200000",
    "2001..10000",
    "501..2000",
    "100..500",
]

DEFAULT_PER_LANGUAGE = 12
DEFAULT_MAX_RESULTS = 100
DEFAULT_BASE_QUALIFIERS = "fork:false archived:false"
DEFAULT_COHORT_NAME = "jvm_skewed_v1"


def discover_language_stratified(
    *,
    languages: list[str],
    base_qualifiers: str,
    per_language: int,
    max_results: int,
    star_bands: list[str],
) -> tuple[list[dict], list[dict]]:
    """Sweep ``language:<lang>`` x star bands. Returns (records, query_meta).

    Records preserve the matching language so callers can audit the
    cohort distribution.
    """
    seen: dict[str, dict] = {}
    queries_meta: list[dict] = []
    for language in languages:
        if len(seen) >= max_results:
            break
        accepted_in_lang = 0
        # GitHub's language: qualifier expects no quoting, but values
        # with a non-letter character (e.g. "F#", "C++") must be quoted.
        if any(c in language for c in "+# "):
            lang_qualifier = f'language:"{language}"'
        else:
            lang_qualifier = f"language:{language}"
        for band in star_bands:
            if accepted_in_lang >= per_language or len(seen) >= max_results:
                break
            base = " ".join(
                part for part in base_qualifiers.split()
                if not part.startswith("stars:")
            )
            q = f"{lang_qualifier} {base} stars:{band}".strip()
            needed = min(per_language - accepted_in_lang, max_results - len(seen))
            items, metas = _search_paginated(query=q, needed=needed)
            accepted = _accept_items(
                items,
                topic=language,
                star_band=band,
                seen=seen,
                curated=set(),
                per_topic_cap=per_language,
                accepted_in_topic=accepted_in_lang,
            )
            accepted_in_lang += accepted
            for m in metas:
                m["accepted"] = accepted if m is metas[-1] else 0
                queries_meta.append(m)
    return list(seen.values()), queries_meta


def main() -> int:
    languages_env = os.environ.get("LANGUAGE_COHORT_LANGUAGES")
    languages = (
        [s.strip() for s in languages_env.split(",") if s.strip()]
        if languages_env
        else DEFAULT_LANGUAGES
    )
    per_language = max(1, int(os.environ.get("LANGUAGE_COHORT_PER_LANG", DEFAULT_PER_LANGUAGE)))
    max_results = max(1, int(os.environ.get("LANGUAGE_COHORT_MAX_RESULTS", DEFAULT_MAX_RESULTS)))
    star_bands_env = os.environ.get("LANGUAGE_COHORT_STAR_BANDS")
    star_bands = (
        [s.strip() for s in star_bands_env.split(",") if s.strip()]
        if star_bands_env
        else DEFAULT_STAR_BANDS
    )
    base_qualifiers = os.environ.get(
        "LANGUAGE_COHORT_BASE_QUALIFIERS",
        DEFAULT_BASE_QUALIFIERS,
    )
    cohort_name = os.environ.get("LANGUAGE_COHORT_NAME", DEFAULT_COHORT_NAME)
    out_path_env = os.environ.get(
        "LANGUAGE_COHORT_OUT",
        f"data/cohorts/{cohort_name}.json",
    )
    out_path = Path(out_path_env)
    if not out_path.is_absolute():
        out_path = REPO_ROOT / out_path

    if not os.environ.get("GITHUB_TOKEN"):
        print(
            "warning: GITHUB_TOKEN unset — language search rate limit will be very low",
            file=sys.stderr,
        )

    records, queries_meta = discover_language_stratified(
        languages=languages,
        base_qualifiers=base_qualifiers,
        per_language=per_language,
        max_results=max_results,
        star_bands=star_bands,
    )

    # Stable ordering: by language then by descending stars.
    records.sort(key=lambda r: (r["matched_topic"], -int(r["stars"])))
    repos = [r["full_name"] for r in records]

    by_language: dict[str, int] = {}
    for r in records:
        by_language[r["matched_topic"]] = by_language.get(r["matched_topic"], 0) + 1

    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "cohort_name": cohort_name,
        "query": {
            "languages": languages,
            "per_language": per_language,
            "base_qualifiers": base_qualifiers,
            "star_bands": star_bands,
        },
        "max_results": max_results,
        "size": len(repos),
        "by_language": dict(sorted(by_language.items(), key=lambda kv: -kv[1])),
        "repos": repos,
        "records": records,
        "search_meta": queries_meta,
    }
    out_path.write_text(json.dumps(doc, indent=2))
    print(
        f"Wrote {len(repos)} repos (across {len(by_language)} languages) → {out_path}",
        flush=True,
    )
    for lang, n in doc["by_language"].items():
        print(f"  {lang:12} {n:3d}", flush=True)
    if not repos:
        print("warning: no repos discovered — check token / languages / qualifiers", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
