#!/usr/bin/env python3
"""Discover public GitHub repos for the experiment / scaled-out pool.

Modes:

* **Daily experiment pool** (legacy default): up to ~100 repos, refreshed
  every CI run, excludes the curated `TARGET_REPOS` from `scan.py`.
* **Scaled-out dataset (Phase 2)**: up to ~1000 repos for the article-3
  rewrite. Driven by `DISCOVER_MAX_RESULTS=1000` plus star-band sweep.

Implementation notes:

* The GitHub Search API caps any single query at **1000** results
  (paginated 100 per page). We side-step that ceiling by sweeping
  star-band qualifiers (e.g. ``stars:500..2000``,
  ``stars:2001..10000``) per topic. Each band acts as a separate
  query, so the union can exceed 1000.
* Search is rate-limited (30 req/min authenticated). The script only
  paginates to the depth needed to hit ``DISCOVER_MAX_RESULTS``,
  which keeps a 1000-repo run well under the budget.
* The curated `TARGET_REPOS` set is excluded so the experiment cohort
  doesn't double-count anchor repos. To use this script as the
  community-dataset producer, set ``DISCOVER_INCLUDE_CURATED=1`` to
  prepend the anchor cohort to the output (then dedupe).

Outputs:

* ``data/experiment_repos.json`` — the discovered list + run metadata.
* ``data/dataset_<size>.json`` (when ``DISCOVER_DATASET_OUT`` is set)
  — versioned dataset artefact for the article rewrite.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"
OUT_PATH = DATA_DIR / "experiment_repos.json"

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE = "https://api.github.com"
HEADERS: dict[str, str] = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "agent-readiness-leaderboard/discover/1.0",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

# GitHub repo search does NOT support `topic:a OR topic:b` (validation error
# or zero hits). We issue one search per topic and merge.
DEFAULT_TOPICS = [
    "llm",
    "llms",
    "agents",
    "agent",
    "ai-agents",
    "mcp",
    "rag",
    "langchain",
    "llmops",
    "llm-inference",
    "vector-database",
    "prompt-engineering",
]
DEFAULT_QUALIFIERS = "fork:false archived:false stars:500..80000"

# Star bands used by the scaled-out (Phase 2) discovery path. Each band
# becomes a separate query per topic so the union can exceed GitHub's
# 1000-per-query cap. Bands are intentionally non-overlapping; the high
# band caps at 200000 to catch the small handful of very-large frameworks.
DEFAULT_STAR_BANDS = [
    "200..1000",
    "1001..5000",
    "5001..20000",
    "20001..200000",
]


def _load_curated() -> set[str]:
    spec = importlib.util.spec_from_file_location("ar_scan", REPO_ROOT / "scripts" / "scan.py")
    if not spec or not spec.loader:
        raise RuntimeError("Could not load scripts/scan.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    names = getattr(mod, "TARGET_REPOS", None)
    if not isinstance(names, list):
        raise RuntimeError("scan.TARGET_REPOS missing")
    return {str(x).lower() for x in names}


def _search_once(
    *,
    query: str,
    per_page: int,
    page: int = 1,
) -> tuple[list[dict], dict]:
    """One Search API call. Returns (raw_items, meta)."""
    url = f"{BASE}/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": per_page,
        "page": page,
    }
    r = requests.get(url, headers=HEADERS, params=params, timeout=60)
    meta = {"http_status": r.status_code, "query": query, "page": page}
    if r.status_code != 200:
        meta["error"] = (r.text or "")[:500]
        return [], meta
    payload = r.json()
    meta["total_count"] = payload.get("total_count")
    meta["incomplete_results"] = payload.get("incomplete_results")
    return payload.get("items") or [], meta


def _search_paginated(
    *,
    query: str,
    needed: int,
) -> tuple[list[dict], list[dict]]:
    """Page through `query` until we collect `needed` items or hit the cap.

    GitHub's Search API caps total results at 1000 per query (10 pages
    of 100). We respect that ceiling and stop early once we have enough.
    """
    per_page = 100
    items: list[dict] = []
    metas: list[dict] = []
    max_pages = 10  # API-enforced ceiling
    for page in range(1, max_pages + 1):
        if len(items) >= needed:
            break
        page_items, meta = _search_once(query=query, per_page=per_page, page=page)
        metas.append(meta)
        if not page_items:
            break
        items.extend(page_items)
        if len(page_items) < per_page:
            break
    return items[:needed] if needed > 0 else items, metas


def _accept_items(
    items: list[dict],
    *,
    topic: str,
    star_band: str | None,
    seen: dict[str, dict],
    curated: set[str],
    per_topic_cap: int,
    accepted_in_topic: int,
) -> int:
    """Mutates `seen`. Returns the count newly accepted from `items`."""
    accepted = 0
    for it in items:
        fn = it.get("full_name")
        if not fn or not isinstance(fn, str):
            continue
        key = fn.lower()
        if key in curated or key in seen:
            continue
        if accepted_in_topic + accepted >= per_topic_cap:
            break
        seen[key] = {
            "full_name": fn,
            "stars": int(it.get("stargazers_count") or 0),
            "matched_topic": topic,
            "matched_star_band": star_band,
        }
        accepted += 1
    return accepted


def discover_multi(
    *,
    topics: list[str],
    qualifiers: str,
    per_topic: int,
    max_results: int,
    curated: set[str],
    star_bands: list[str] | None = None,
) -> tuple[list[str], list[dict]]:
    """Discover up to `max_results` repos by sweeping topics x star bands.

    For small `max_results` (<=100), behaves like the legacy single-page
    path. For large `max_results` (e.g. 1000), it paginates each query
    and sweeps `star_bands` so the union can exceed GitHub's 1000-per-
    query cap.
    """
    seen: dict[str, dict] = {}
    queries_meta: list[dict] = []
    use_bands = bool(star_bands) and max_results > 100

    for topic in topics:
        if len(seen) >= max_results:
            break
        accepted_in_topic = 0
        if use_bands:
            assert star_bands is not None  # for type-checkers
            for band in star_bands:
                if accepted_in_topic >= per_topic or len(seen) >= max_results:
                    break
                # Strip any star qualifier the caller passed in `qualifiers`,
                # since we're injecting our own band-scoped one.
                base = " ".join(
                    part
                    for part in qualifiers.split()
                    if not part.startswith("stars:")
                )
                q = f"topic:{topic} {base} stars:{band}".strip()
                needed = min(per_topic - accepted_in_topic, max_results - len(seen))
                items, metas = _search_paginated(query=q, needed=needed)
                accepted = _accept_items(
                    items,
                    topic=topic,
                    star_band=band,
                    seen=seen,
                    curated=curated,
                    per_topic_cap=per_topic,
                    accepted_in_topic=accepted_in_topic,
                )
                accepted_in_topic += accepted
                for m in metas:
                    m["accepted"] = accepted if m is metas[-1] else 0
                    queries_meta.append(m)
        else:
            q = f"topic:{topic} {qualifiers}".strip()
            needed = min(per_topic, max_results - len(seen))
            items, metas = _search_paginated(query=q, needed=needed)
            accepted = _accept_items(
                items,
                topic=topic,
                star_band=None,
                seen=seen,
                curated=curated,
                per_topic_cap=per_topic,
                accepted_in_topic=accepted_in_topic,
            )
            for m in metas:
                m["accepted"] = accepted if m is metas[-1] else 0
                queries_meta.append(m)

    ranked = sorted(seen.values(), key=lambda x: -x["stars"])[:max_results]
    return [r["full_name"] for r in ranked], queries_meta


def main() -> int:
    legacy_query = os.environ.get("DISCOVER_SEARCH_QUERY")
    topics_env = os.environ.get("DISCOVER_TOPICS")
    topics = (
        [t.strip() for t in topics_env.split(",") if t.strip()]
        if topics_env
        else DEFAULT_TOPICS
    )
    qualifiers = os.environ.get("DISCOVER_QUALIFIERS", DEFAULT_QUALIFIERS)
    per_topic = max(1, int(os.environ.get("DISCOVER_PER_TOPIC", "25")))
    # Ceiling raised from 100 → 2000 so Phase 2 (1000-repo dataset) can
    # use this same script. Daily CI still defaults to 100.
    max_results = int(os.environ.get("DISCOVER_MAX_RESULTS", "100"))
    max_results = max(1, min(max_results, 2000))
    star_bands_env = os.environ.get("DISCOVER_STAR_BANDS")
    star_bands = (
        [b.strip() for b in star_bands_env.split(",") if b.strip()]
        if star_bands_env
        else DEFAULT_STAR_BANDS
    )
    include_curated = os.environ.get("DISCOVER_INCLUDE_CURATED", "0") == "1"
    dataset_out_env = os.environ.get("DISCOVER_DATASET_OUT")

    if not GITHUB_TOKEN:
        print("warning: GITHUB_TOKEN unset — search rate limit will be low", file=sys.stderr)

    curated = _load_curated()
    # When producing a community dataset (Phase 2) we want anchor repos
    # *included*, not excluded; when refreshing the daily experiment
    # cohort we exclude them so we don't double-count.
    effective_curated = set() if include_curated else curated

    if legacy_query:
        items, metas = _search_paginated(query=legacy_query, needed=max_results)
        repos: list[str] = []
        for it in items:
            fn = it.get("full_name")
            if isinstance(fn, str) and fn.lower() not in effective_curated:
                repos.append(fn)
                if len(repos) >= max_results:
                    break
        queries_meta = metas
    else:
        repos, queries_meta = discover_multi(
            topics=topics,
            qualifiers=qualifiers,
            per_topic=per_topic,
            max_results=max_results,
            curated=effective_curated,
            star_bands=star_bands,
        )

    if include_curated:
        # Prepend curated anchors (preserves their ordering from
        # scan.TARGET_REPOS) and dedupe.
        anchors = [name for name in sorted(curated) if name not in {r.lower() for r in repos}]
        repos = anchors + repos
        repos = repos[:max_results]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    doc = {
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "query": legacy_query
        or {
            "topics": topics,
            "qualifiers": qualifiers,
            "per_topic": per_topic,
            "star_bands": star_bands if max_results > 100 else None,
            "include_curated": include_curated,
        },
        "max_results": max_results,
        "repos": repos,
        "search_meta": queries_meta,
    }
    OUT_PATH.write_text(json.dumps(doc, indent=2))
    print(f"Wrote {len(repos)} repos → {OUT_PATH}")
    if dataset_out_env:
        out2 = Path(dataset_out_env)
        if not out2.is_absolute():
            out2 = REPO_ROOT / out2
        out2.parent.mkdir(parents=True, exist_ok=True)
        out2.write_text(json.dumps(doc, indent=2))
        print(f"Wrote {len(repos)} repos → {out2} (dataset artefact)")
    if not repos:
        print("warning: no repos discovered — check token / topics / qualifiers", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
