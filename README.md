# agent-readiness-leaderboard

Public leaderboard: curated high-signal AI/agent repos plus a **daily experiment pool** (GitHub Search) scanned with [`agent-readiness`](https://github.com/harrydaihaolin/agent-readiness).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

Serve the static site locally (from repo root):

```bash
python3 -m http.server 8080
# open http://127.0.0.1:8080/
```

Regenerate curated scores (requires a configured environment — see Scripts below):

```bash
python3 scripts/scan.py
```

## Test

```bash
python3 -m py_compile scripts/scan.py scripts/discover_repos.py
```

## Scripts

| Script | Purpose |
|--------|---------|
| [`scripts/scan.py`](scripts/scan.py) | Shallow-clone each target and run `agent-readiness scan --json` → `data/scores.json` (curated default) |
| [`scripts/discover_repos.py`](scripts/discover_repos.py) | GitHub Search API → up to **100** public repos (excludes curated list) → `data/experiment_repos.json` |

### `scan.py` modes

- **Default / `-o data/scores.json`** — Curated `TARGET_REPOS` only.
- **`--with-experiment`** — Curated plus repos listed in `data/experiment_repos.json`.
- **`--experiment-only -o data/scores_experiment.json`** — Scan only the daily pool (used in CI after `discover_repos.py`).

## Daily experiment pool (environment)

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | Required for Search API rate limits and repo metadata in `scan.py` |
| `DISCOVER_SEARCH_QUERY` | Override GitHub `q=` (default: public repos with agent/LLM/MCP/RAG topics, 500–80k stars) |
| `DISCOVER_MAX_RESULTS` | Cap (1–100, default 100) |

## CI

[`.github/workflows/daily-scan.yml`](.github/workflows/daily-scan.yml) runs **discover → scan curated → scan experiment pool** and commits `data/scores.json`, `data/scores_experiment.json`, and `data/experiment_repos.json`.

Downstream **research** [`judge.py`](../agent-readiness-research/scripts/judge.py) can merge both score files with `--merge-scores` so the rules loop sees friction from the broader pool.
