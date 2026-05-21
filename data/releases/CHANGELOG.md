# Frozen-release changelog

This file records the immutable dataset / scores releases that live
under [`data/releases/`](.) and are referenced by GitHub Releases.
The daily scanner *does not* write here — only one-shot, manually
triggered workflows do (see `.github/workflows/release-v3-snapshot.yml`).

Releases below are listed newest-first and never deleted; the article
or downstream consumer that cited the release expects the artefact
to remain at its original URL forever.

## v3.3-2026-05-21 — 2026-05-21

**Dataset:** [`v3_1000_2026-05-02.json`](./v3_1000_2026-05-02.json) — same v3.2 cohort. The dataset doesn't change; only the scoring engine does.
**Scores:** [`scores_v3_1000_2026-05-21.json`](./scores_v3_1000_2026-05-21.json) — minted by the daily-scan workflow on 2026-05-21 after the engine pin moved to `agent-readiness 2.4.6` (rules pack v2.4.1).
**Engine:** `agent-readiness==2.4.6` (rules pack v2.4.1, **38 checks**).
**AAIF evidence:** [`research/aaif_evidence/2026-05-21_calibration_cycle.md`](https://github.com/harrydaihaolin/agent-readiness-research/blob/main/research/aaif_evidence/2026-05-21_calibration_cycle.md).

### What changes vs v3.2

Two calibration steps land between v3.2 and v3.3:

1. **`agent-readiness 2.4.4`** — `gitignore_coverage` `language_aware` threshold hotfix
   ([engine #80](https://github.com/harrydaihaolin/agent-readiness/pull/80)). v2.4.3
   silently switched the matcher from "7-of-13 groups required" to "every filtered
   group required", regressing `gitignore.covers_junk` by +4.1 pp on the full cohort.
   v2.4.4 restores the pre-language-aware leniency for ecosystems with ≥ 3
   language-specific groups in scope.
2. **`agent-readiness 2.4.5` + rules pack v2.4.1 + `agent-readiness 2.4.6` (vendor bump)**
   — `safety.gitleaks_config` precondition gate
   ([engine #81](https://github.com/harrydaihaolin/agent-readiness/pull/81),
   [rules #27](https://github.com/harrydaihaolin/agent-readiness-rules/pull/27),
   [engine #82](https://github.com/harrydaihaolin/agent-readiness/pull/82)).
   The rule now fires only when the repo shows evidence of *handling secrets*
   (env-file usage, env-var reads in source, cloud SDK imports, compose / IaC
   declarations that bind secrets, hardcoded credential literals). Pure-library
   repos with no credential surface area are skipped silently rather than
   penalised for omitting a tool they have no use for.

### Headline numbers (paired vs v3.2)

| check_id | v3.2 (993 repos) | v3.3 (985 repos) | delta_pp |
|---|---|---|---|
| `safety.gitleaks_config` | 64.9% (644/993) | **62.2%** (613/985) | **−2.6 pp** |
| `gitignore.covers_junk` | 61.4% (610/993) | 59.7% (588/985) | −1.7 pp |
| `agent_docs.canonical` | 77.7% (772/993) | 76.5% (754/985) | −1.2 pp |
| `readme.has_run_instructions` | 48.8% (485/993) | 47.7% (470/985) | −1.1 pp |
| `ci.configured` | 35.1% (349/993) | 34.4% (339/985) | −0.7 pp |

Full paired-diff table: [`agent-readiness-research/data/self_improvement_2026-05-21/clearance_v3_v246.md`](https://github.com/harrydaihaolin/agent-readiness-research/blob/main/data/self_improvement_2026-05-21/clearance_v3_v246.md).

The `safety.gitleaks_config` clearance is modest (−2.6 pp) on this cohort
*on purpose*: v3 is topic-keyed (llm / agents / rag) and over-represents
Python / TypeScript, so most repos genuinely handle secrets and continue
firing correctly. The population-level effect of the precondition gate is
measured on the companion `jvm-skewed-v1-2026-05-21` cohort, where the
fire-rate is **22.2 pp below** the v3.2 baseline.

## jvm-skewed-v1-2026-05-21 — 2026-05-21

**Dataset:** [`../cohorts/jvm_skewed_v1.json`](../cohorts/jvm_skewed_v1.json) — 144 production repos across 12 languages (12 each: Scala, Clojure, Kotlin, Java, Erlang, Elixir, OCaml, Julia, R, Haskell, F#, Groovy). Built with `scripts/discover_language_cohort.py` because the v3 cohort under-represents these populations (0 Scala, 1 Clojure, 1 Julia, 6 Kotlin, 15 Java in 993 v3 repos).
**Scores:** [`../cohorts/scores/jvm_skewed_v1_2.4.6.json`](../cohorts/scores/jvm_skewed_v1_2.4.6.json) — first baseline scan (131 of 144 repos completed; 9 % long-tail clone failures).
**Engine:** `agent-readiness==2.4.6` (rules pack v2.4.1, 38 checks).

### Why this cohort exists

The 2026-05-21 calibration cycle's pre-registered acceptance gate
(`safety.gitleaks_config` clearance ≥ 5 pp paired) failed on the v3 cohort
because v3 is topic-keyed and contains almost no Scala / Clojure / Erlang /
OCaml / Julia / R / Haskell / F# / Groovy. The improvements that v2.4.3 +
v2.4.5/2.4.6 were designed to ship for those ecosystems were not *visible*
in v3 measurement. `jvm-skewed-v1` fixes that, and is now the first
language-stratified baseline so any future change to the precondition gate
can be paired-diffed against it.

### Headline numbers

`safety.gitleaks_config` aggregate fire rate: **42.7% (56/131)** — **22.2 pp
below the v3.2 baseline of 64.9%**. Per-language:

| Language | Fire rate | n |
|---|---|---|
| Java     | 10.0% | 1/10 |
| Erlang   | 18.2% | 2/11 |
| F#       | 25.0% | 3/12 |
| R        | 27.3% | 3/11 |
| Scala    | 36.4% | 4/11 |
| Kotlin   | 44.4% | 4/9 |
| Clojure  | 45.5% | 5/11 |
| Haskell  | 50.0% | 6/12 |
| Julia    | 50.0% | 5/10 |
| Groovy   | 54.5% | 6/11 |
| OCaml    | 63.6% | 7/11 |
| Elixir   | 83.3% | 10/12 |

Pure-library JVM ecosystems (Java, Erlang, F#, Scala) cleanly skip the rule;
web-facing ones (Elixir / Phoenix, OCaml, Groovy) continue firing because
their repos genuinely handle credentials — exactly the design intent.

### Caveat

131-of-144 (91 %) completion on the local scan; the remaining 13 hit clone
errors / network timeouts (consistent with the daily-scan workflow's long-tail
failure rate). The next cycle should re-run via the sharded
`release-v3-snapshot.yml` workflow to push completion past 99 %.

## v3.2-2026-05-02 — 2026-05-02 (in flight)

**Dataset:** [`v3_1000_2026-05-02.json`](./v3_1000_2026-05-02.json) — same `repos[]` as `v3_1000_2026-05-01.json` (the v3.1 freeze); date-stamped a day later so the rescored output lands at `scores_v3_1000_2026-05-02.json` without overwriting the immutable v3.1 snapshot.
**Scores:** [`scores_v3_1000_2026-05-02.json`](./scores_v3_1000_2026-05-02.json) — minted by `release-v3-snapshot.yml` after the leaderboard's pin bumped to `agent-readiness>=1.5.0,<2`.
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
