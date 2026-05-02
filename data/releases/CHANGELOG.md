# Frozen-release changelog

This file records the immutable dataset / scores releases that live
under [`data/releases/`](.) and are referenced by GitHub Releases.
The daily scanner *does not* write here — only one-shot, manually
triggered workflows do (see `.github/workflows/release-v3-snapshot.yml`).

Releases below are listed newest-first and never deleted; the article
or downstream consumer that cited the release expects the artefact
to remain at its original URL forever.

## v3.2 — pending (2026-05-XX)

**Dataset:** same cohort as v3-2026-05-01 (`v3_1000_2026-05-01.json`).
**Scores:** `scores_v3_1000_2026-05-XX.json` (pending; will be cut by `release-v3-snapshot.yml` once `agent-readiness 1.5.0` lands on PyPI and this leaderboard's pin bumps).
**Engine:** `agent-readiness>=1.5.0,<2` (rules pack v1.5.0, **38 checks**).

### What changes vs v3.1

* Rules pack v1.5.0 ships one calibration: `repo_shape.large_files` thresholds bump from 500 lines / 50 KB to 1500 lines / 150 KB. Target band 30–60% (was 88.1% on v3.1, no longer discriminating). Production fire rate confirmation is the explicit gate of this snapshot.
* New community-contributed check: `cognitive_load.readme_root_present`. Low expected fire rate (most cohort repos already have a root README).
* No other rule changes; the rest of the v3.1 ideas backlog ([`agent-readiness-research/research/ideas.archive.md`](https://github.com/harrydaihaolin/agent-readiness-research/blob/main/research/ideas.archive.md)) is closed out as deferred-with-rationale (engine matcher gap or research-grade gate per item).

### v3.2 release gate

If `repo_shape.large_files` lands outside 30–60% on the v3.2 snapshot, a `agent-readiness 1.5.1` patches thresholds further; this `v3.2` slot stays "pending" until the gate clears.

## v3-2026-05-01 — 2026-05-02

**Dataset:** [`v3_1000_2026-05-01.json`](./v3_1000_2026-05-01.json)
**Scores:** [`scores_v3_1000_2026-05-01.json`](./scores_v3_1000_2026-05-01.json) (engine `agent-readiness>=1.4.0,<2`, rules pack v1.4.0, 37 checks)
**Prior pin:** [`scores_v3_1000_2026-05-01.v100.json`](./scores_v3_1000_2026-05-01.v100.json) (engine 1.1.0, rules pack v1.0.0, 7 checks) — preserved for the v1.0.0 → v1.4.0 diff cited in the article.
**Article:** [`scanning-1000-ai-repos-v3`](https://github.com/harrydaihaolin/agent-readiness-research/blob/main/research/scanning-1000-ai-repos-v3.draft.md).

### Dataset
- 1000 unique repos discovered across 9 AI / agent topics × 4 star
  bands (`200..1000`, `1001..5000`, `5001..20000`, `20001..200000`),
  curated `TARGET_REPOS` anchors included
  (`DISCOVER_INCLUDE_CURATED=1`).
- Reproducible via `scripts/discover_repos.py` (see
  [`README.md`](./README.md) for the recipe).

### Scores
- Sharded scan via the matrix `release-v3-snapshot.yml` workflow
  (default 4 shards). Matches `scripts/scan.py --shard k/N` +
  `scripts/merge_shards.py` exactly so re-runs are reproducible.
- Wall-clock time: ~10 min (4 shards × ~6-7 min each + ~2 min merge);
  was 25 min unsharded.
- Schema-validated against `schemas/scores.schema.json` before
  commit; `merge_shards.py` rejects partial inputs.

### Headline numbers
See the article for the full discussion. Key: 67.7% of 994 successfully
scanned repos miss `agent_docs.present` (replicates v2's 64% at 10×
the cohort size). Stratified tables by star band + language live in
the article body.

## v3-prelim-30 — 2026-05-01

**Dataset slice:** [`v3_sample30_2026-05-01.json`](./v3_sample30_2026-05-01.json) — deterministic 30-repo subsample of `v3_1000_2026-05-01.json` for fast schema / pipeline validation before the full run.
**Scores:** [`scores_v3_sample30_2026-05-01.json`](./scores_v3_sample30_2026-05-01.json).
**Health:** [`scan_health_v3_sample30.json`](./scan_health_v3_sample30.json).

Used during the v3 article's draft phase to confirm the scan path
worked end-to-end (0 failures, 30/30 scanned) against the
`agent-readiness 1.1.0` engine before the cohort was scaled to 1000.
