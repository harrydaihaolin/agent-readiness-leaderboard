#!/usr/bin/env python3
"""
Discover fresh public GitHub repos for the daily experiment pool.

Uses the GitHub Search API (up to 100 results per run), excludes repos already
in the curated TARGET_REPOS list from scripts/scan.py, and writes
data/experiment_repos.json for scan.py (--experiment-only / --with-experiment).

Requires GITHUB_TOKEN in CI (or local) for usable rate limits.
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
) -> tuple[list[dict], dict]:
    """One Search API call. Returns (raw_items, meta)."""
    url = f"{BASE}/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page}
    r = requests.get(url, headers=HEADERS, params=params, timeout=60)
    meta = {"http_status": r.status_code, "query": query}
    if r.status_code != 200:
        meta["error"] = (r.text or "")[:500]
        return [], meta
    payload = r.json()
    meta["total_count"] = payload.get("total_count")
    meta["incomplete_results"] = payload.get("incomplete_results")
    return payload.get("items") or [], meta


def discover_multi(
    *,
    topics: list[str],
    qualifiers: str,
    per_topic: int,
    max_results: int,
    curated: set[str],
) -> tuple[list[str], list[dict]]:
    seen: dict[str, dict] = {}
    queries_meta: list[dict] = []
    for topic in topics:
        q = f"topic:{topic} {qualifiers}".strip()
        items, meta = _search_once(query=q, per_page=min(100, per_topic))
        meta["accepted"] = 0
        for it in items[:per_topic]:
            fn = it.get("full_name")
            if not fn or not isinstance(fn, str):
                continue
            if fn.lower() in curated:
                continue
            if fn.lower() in seen:
                continue
            seen[fn.lower()] = {
                "full_name": fn,
                "stars": int(it.get("stargazers_count") or 0),
                "matched_topic": topic,
            }
            meta["accepted"] += 1
        queries_meta.append(meta)

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
    max_results = int(os.environ.get("DISCOVER_MAX_RESULTS", "100"))
    max_results = max(1, min(max_results, 100))

    if not GITHUB_TOKEN:
        print("warning: GITHUB_TOKEN unset — search rate limit will be low", file=sys.stderr)

    curated = _load_curated()

    if legacy_query:
        items, meta = _search_once(query=legacy_query, per_page=min(100, max_results))
        repos: list[str] = []
        for it in items:
            fn = it.get("full_name")
            if isinstance(fn, str) and fn.lower() not in curated:
                repos.append(fn)
                if len(repos) >= max_results:
                    break
        queries_meta = [meta]
    else:
        repos, queries_meta = discover_multi(
            topics=topics,
            qualifiers=qualifiers,
            per_topic=per_topic,
            max_results=max_results,
            curated=curated,
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    doc = {
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "query": legacy_query or {"topics": topics, "qualifiers": qualifiers, "per_topic": per_topic},
        "max_results": max_results,
        "repos": repos,
        "search_meta": queries_meta,
    }
    OUT_PATH.write_text(json.dumps(doc, indent=2))
    print(f"Wrote {len(repos)} repos → {OUT_PATH}")
    if not repos:
        print("warning: no repos discovered — check token / topics / qualifiers", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
