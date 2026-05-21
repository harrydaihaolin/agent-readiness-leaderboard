# Language-stratified cohorts

The default `data/dataset_1000.json` (used by Phase 2 of the article
rewrite and the daily-scan workflow) is built from topic-keyed queries
(`llm`, `agents`, `rag`, …). That biases the corpus toward Python /
TypeScript and under-represents the language populations that recent
calibration cycles want to measure improvements against.

This directory holds **language-keyed** cohorts produced by
[`scripts/discover_language_cohort.py`](../../scripts/discover_language_cohort.py),
frozen as versioned JSON artefacts so paired diffs across calibration
cycles target the same repos.

## Cohorts

| Cohort | Languages | Size | Provenance |
|---|---|---|---|
| `jvm_skewed_v1.json` | Scala, Clojure, Kotlin, Java, Erlang, Elixir, OCaml, Julia, R, Haskell, F#, Groovy | 144 (12 / language) | Built 2026-05-21 to validate `agent-readiness 2.4.3` (language-aware matchers) and 2.4.4 (gitignore_coverage threshold fix) on populations the v3 cohort missed. Companion to `aaif_evidence/2026-05-21_calibration_cycle.md` follow-up #2. |

## Why this exists

The 2026-05-21 calibration cycle measured paired diffs of `agent-readiness 2.4.3`
against `v1.5.0` on the v3 cohort (993 repos) and found **no clearance** for
the two pre-registered targets (`safety.gitignore.covers_junk`,
`feedback.manifest.detected`). The root cause was cohort skew, not engine
regression: v3 contains 0 Scala, 1 Clojure, 1 Julia, 6 Kotlin, 15 Java in
993 repos, so improvements designed for those ecosystems were not
*visible* in measurement. This cohort fixes that.

## Format

Each cohort file shares the same shape as `dataset_1000.json` plus a
`by_language` histogram so audits can confirm the stratification held:

```json
{
  "updated_at": "2026-05-21T...Z",
  "cohort_name": "jvm_skewed_v1",
  "query": {"languages": [...], "per_language": 12, "star_bands": [...]},
  "size": 144,
  "by_language": {"Scala": 12, "Clojure": 12, ...},
  "repos": ["org/name", ...],
  "records": [{"full_name": ..., "stars": ..., "matched_topic": ..., "matched_star_band": ...}, ...],
  "search_meta": [...]
}
```

## Regenerating

Cohorts are intended to be **frozen** — paired diffs require the same
repo list between calibration cycles. Re-run the discoverer only when
deliberately bumping the cohort version (e.g. `jvm_skewed_v2`):

```bash
export GITHUB_TOKEN=$(gh auth token)
# Full default (12 languages, 12 per, 150 cap):
python3 scripts/discover_language_cohort.py

# Custom (e.g. add Rust as a control):
LANGUAGE_COHORT_LANGUAGES="Scala,Clojure,Rust" \
LANGUAGE_COHORT_PER_LANG=20 \
LANGUAGE_COHORT_MAX_RESULTS=60 \
LANGUAGE_COHORT_OUT=data/cohorts/scala_clojure_rust_v1.json \
python3 scripts/discover_language_cohort.py
```

## Using a cohort with `scan.py`

```bash
agent-readiness-leaderboard/scripts/scan.py \
  --experiment-only \
  --experiment-json data/cohorts/jvm_skewed_v1.json \
  --out data/cohorts/jvm_skewed_v1_scores.json
```
