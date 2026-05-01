# AGENTS.md — agent-readiness-leaderboard

The public leaderboard: curated AI/agent repos plus a daily-discovered
experiment pool, scanned by `agent-readiness` and rendered as a small
static site under GitHub Pages.

## Canonical commands

| Task | Command |
|---|---|
| Install (Python deps) | `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` |
| Serve site locally | `python3 -m http.server 8080` (opens `http://127.0.0.1:8080/`) |
| Regenerate curated scores | `python3 scripts/scan.py -o data/scores.json` |
| Discover daily experiment pool | `python3 scripts/discover_repos.py` |
| Scan experiment-only | `python3 scripts/scan.py --experiment-only -o data/scores_experiment.json` |
| Lint | `ruff check scripts/` |
| Test (compile-only) | `python3 -m py_compile scripts/*.py` |
| Self-scan | `agent-readiness scan . --fail-below 90` |

The self-scan threshold matches `.github/workflows/ci.yml`. Bump it in
both files in the same PR if rule additions allow it.

## CI and the feedback loop

**CI is part of the feedback loop.** After you push or update a PR,
**monitor GitHub Actions / workflow runs and check results**. When
**CI fails**, read the logs, **fix the root cause**, and push
follow-up commits. Do not stop while checks are red or ignore failing
workflows.

Two workflows live here:

- `daily-scan.yml` — cron at 06:00 UTC; rebuilds `data/scores.json`,
  `data/scores_experiment.json`, `data/experiment_repos.json`.
- `ci.yml` — runs on push and PR; lints, byte-compiles scripts, and
  self-scans this repo against `--fail-below`.

## Do-not-touch

- **`data/` snapshots are written by CI.** Do **not** commit changes to
  `data/scores.json`, `data/scores_experiment.json`, or
  `data/experiment_repos.json` by hand. The `daily-scan.yml` workflow
  is the only writer; manual edits will be overwritten on the next run
  and may flap downstream consumers (research repo's `judge.py`).
- `index.html` is the deployed entrypoint. Don't move it.
- Don't hardcode tokens in scripts; everything reads `GITHUB_TOKEN`
  from the environment.

## Headless contract

`scripts/scan.py` and `scripts/discover_repos.py` are fully
non-interactive. They read `GITHUB_TOKEN` from the environment and
emit JSON; nothing in the loop expects a TTY or prompts the user.

## Where to look

- `README.md` — human-facing overview, install, run.
- `CONTRIBUTING.md` — how to propose changes.
- `SECURITY.md` — how to report vulnerabilities.
- `scripts/scan.py` — the canonical entry point. Read this first if
  you're touching scoring logic.
