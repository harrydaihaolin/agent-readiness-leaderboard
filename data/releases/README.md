# Frozen dataset releases

Files in this directory are **immutable**. They are referenced by name
from research articles (e.g. `scanning-1000-ai-repos-v3`) and
expected to keep their content identical for the lifetime of the
article. The daily scanner does not write here — only one-shot,
manually-triggered workflows do.

## Naming

`v<article-version>_<size>_<YYYY-MM-DD>.json`

Example: `v3_1000_2026-05-01.json` — the 1000-repo cohort underlying
the v3 rewrite of "scanning AI repos", frozen on 2026-05-01.

## Schema

Same envelope produced by [`scripts/discover_repos.py`](../../scripts/discover_repos.py):

```json
{
  "updated_at": "<ISO timestamp>",
  "query": { "topics": [...], "qualifiers": "...", "star_bands": [...] },
  "max_results": 1000,
  "repos": ["owner/name", ...],
  "search_meta": [ { "query": "...", "total_count": ..., "accepted": ... } ]
}
```

`repos` is sorted by stars (descending) at the time of capture and
deduped. The curated `TARGET_REPOS` anchors are included
(`DISCOVER_INCLUDE_CURATED=1`) so the dataset is a strict superset of
the daily leaderboard cohort.

## Reproducing a frozen file

```bash
# Reproduces v3_1000_<date>.json (modulo new repos that have been
# created or starred since the freeze; the freeze itself is what
# gets cited in the article).
GITHUB_TOKEN="$(gh auth token)" \
DISCOVER_MAX_RESULTS=1000 \
DISCOVER_PER_TOPIC=120 \
DISCOVER_INCLUDE_CURATED=1 \
DISCOVER_DATASET_OUT="data/releases/v3_1000_$(date +%F).json" \
python3 scripts/discover_repos.py
```

## Scan replication

To produce the matching `scores.json` snapshot for a frozen dataset,
fire the manual workflow
[`release-v3-snapshot.yml`](../../.github/workflows/release-v3-snapshot.yml)
or run locally:

```bash
agent-readiness --version  # pin this in the article
python3 scripts/scan.py \
  --experiment-only \
  --experiment-json data/releases/v3_1000_2026-05-01.json \
  --output data/releases/scores_v3_1000_2026-05-01.json
```

The article cites the resulting `scores_v3_*.json` by an immutable
GitHub Release URL, not by the path on `main`.

## Engine version pinning convention

When the same dataset is scanned under different engine versions, we
keep both snapshots side by side. The fresher run keeps the canonical
name; older runs are renamed with the engine pack version embedded:

| Snapshot | Engine pack | Created |
| --- | --- | --- |
| `scores_v3_1000_2026-05-01.v100.json` | rules pack v1.0.0 (7 checks) | first v3 freeze, retained for diff vs v1.4.0 |
| `scores_v3_1000_2026-05-01.json` | rules pack v1.4.0 (37 checks) | v3.1 rerun on `agent-readiness>=1.4.0` |

`scripts/release_diff.py` (in `agent-readiness-research`) consumes both
files to render the v1.0 → v1.4 diff cited by the article.
