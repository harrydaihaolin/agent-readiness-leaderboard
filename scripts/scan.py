#!/usr/bin/env python3
"""
Agent Readiness Scanner v2
==========================
Shallow-clones each repo and invokes `agent-readiness scan --json` to score
AI agent infrastructure repos using the official 4-pillar model:

  cognitive_load  — clarity and navigability of the codebase
  feedback        — testing, CI, and observability signals
  flow            — reliability, automation, and contributor experience
  safety          — security posture and responsible-AI signals
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE = "https://api.github.com"
MAX_WORKERS = 8

HEADERS: dict[str, str] = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "agent-readiness-leaderboard/2.0",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

TARGET_REPOS = [
    # ── Agent Frameworks & Orchestration ──────────────────────────────────────
    "langchain-ai/langchain",           # 135k ★  agent engineering platform
    "langchain-ai/langgraph",           # 30k  ★  graph-based agent orchestration
    "microsoft/autogen",                # 57k  ★  multi-agent AI framework
    "crewAIInc/crewAI",                 # 50k  ★  role-playing autonomous agents
    "run-llama/llama_index",            # 49k  ★  data framework for LLM apps
    "FoundationAgents/MetaGPT",         # 67k  ★  multi-agent software company
    "camel-ai/camel",                   # 16k  ★  communicative agents
    "deepset-ai/haystack",              # 25k  ★  LLM orchestration framework
    "pydantic/pydantic-ai",             # 16k  ★  type-safe AI agents
    "stanfordnlp/dspy",                 # 34k  ★  programmatic LLM pipelines
    "letta-ai/letta",                   # 22k  ★  stateful agents with memory
    "microsoft/TaskWeaver",             # 6k   ★  code-first agent framework
    "QwenLM/Qwen-Agent",                # 16k  ★  Qwen-based agent framework
    "TransformerOptimus/SuperAGI",      # 17k  ★  autonomous AI agent framework
    "openai/swarm",                     # 21k  ★  lightweight multi-agent
    "griptape-ai/griptape",             # 2k   ★  modular agent framework
    "Significant-Gravitas/AutoGPT",     # 183k ★  autonomous GPT agent
    "agno-agi/agno",                    # 39k  ★  agent framework (formerly phidata)
    "neuml/txtai",                      # 12k  ★  AI framework for semantic search
    "huggingface/smolagents",           # 26k  ★  minimal agent framework by HF
    "microsoft/promptflow",             # 11k  ★  LLM workflow framework
    "assafelovic/gpt-researcher",       # 26k  ★  autonomous research agent
    "openai/openai-agents-python",      # 25k  ★  OpenAI agents SDK
    "kyegomez/swarms",                  # 6k   ★  multi-agent swarm framework
    "SWE-agent/SWE-agent",              # 19k  ★  software engineering agent
    "OpenHands/OpenHands",              # 72k  ★  open-source coding agent
    "yoheinakajima/babyagi",            # 22k  ★  task-driven autonomous agent
    "OpenBMB/ChatDev",                  # 32k  ★  multi-agent software dev
    "guidance-ai/guidance",             # 21k  ★  constrained LLM generation
    # ── LLM Inference & Serving ───────────────────────────────────────────────
    "vllm-project/vllm",                # 78k  ★  high-throughput LLM inference
    "sgl-project/sglang",               # 13k  ★  structured generation serving
    "ggml-org/llama.cpp",               # 107k ★  C/C++ LLM inference
    "ollama/ollama",                    # 170k ★  local LLM runtime
    "huggingface/text-generation-inference", # 10k ★ TGI serving
    "huggingface/transformers",         # 160k ★  core ML transforms
    "skypilot-org/skypilot",            # 9k   ★  cloud LLM deployment
    "mudler/LocalAI",                   # 45k  ★  local AI inference server
    "nomic-ai/gpt4all",                 # 77k  ★  local LLM desktop runner
    "unslothai/unsloth",                # 63k  ★  fast LLM fine-tuning
    "hiyouga/LlamaFactory",             # 70k  ★  unified LLM fine-tuning
    "oobabooga/text-generation-webui",  # 46k  ★  LLM web UI
    "deepspeedai/DeepSpeed",            # 42k  ★  deep learning optimization
    "mistralai/mistral-inference",      # 10k  ★  Mistral inference engine
    # ── LLM App Platforms ─────────────────────────────────────────────────────
    "langgenius/dify",                  # 139k ★  LLM app development platform
    "open-webui/open-webui",            # 134k ★  local LLM web interface
    # ── LLM SDKs & APIs ───────────────────────────────────────────────────────
    "openai/openai-python",             # 30k  ★  official OpenAI Python SDK
    "anthropics/anthropic-sdk-python",  # 3k   ★  official Anthropic Python SDK
    "BerriAI/litellm",                  # 45k  ★  universal LLM API
    "microsoft/semantic-kernel",        # 27k  ★  LLM integration SDK
    "ComposioHQ/composio",              # 27k  ★  AI tools integration
    "modelcontextprotocol/python-sdk",  # 22k  ★  MCP Python SDK
    "modelcontextprotocol/typescript-sdk", # 12k ★ MCP TypeScript SDK
    "567-labs/instructor",              # 12k  ★  structured LLM outputs
    "vibrantlabsai/ragas",              # 13k  ★  RAG evaluation framework
    # ── Memory & Vector Stores ────────────────────────────────────────────────
    "mem0ai/mem0",                      # 54k  ★  universal memory layer
    "chroma-core/chroma",               # 27k  ★  vector database
    "qdrant/qdrant",                    # 30k  ★  vector search engine
    "weaviate/weaviate",                # 16k  ★  vector + graph DB
    "milvus-io/milvus",                 # 44k  ★  vector database
    "lancedb/lancedb",                  # 10k  ★  multi-modal vector DB
    "activeloopai/deeplake",            # 9k   ★  deep learning data lake
    "milvus-io/pymilvus",               # 1k   ★  Milvus Python SDK
    "microsoft/graphrag",               # 32k  ★  graph-based RAG
    # ── Workflow & Orchestration ──────────────────────────────────────────────
    "apache/airflow",                   # 45k  ★  DAG workflow orchestration
    "ray-project/ray",                  # 42k  ★  distributed compute
    "temporalio/temporal",              # 19k  ★  durable workflow engine
    "celery/celery",                    # 28k  ★  distributed task queue
    "PrefectHQ/prefect",                # 22k  ★  modern workflow orchestration
    "dagster-io/dagster",               # 15k  ★  data orchestration
    "argoproj/argo-workflows",          # 16k  ★  K8s workflow engine
    "kubeflow/kubeflow",                # 15k  ★  ML workflows on K8s
    "kubernetes/kubernetes",            # 112k ★  container orchestration
    "n8n-io/n8n",                       # 185k ★  workflow automation
    # ── Observability & Eval ──────────────────────────────────────────────────
    "langfuse/langfuse",                # 26k  ★  LLM observability platform
    "Arize-ai/phoenix",                 # 9k   ★  AI observability & eval
    "traceloop/openllmetry",            # 7k   ★  LLM observability SDK
    "Helicone/helicone",                # 5k   ★  LLM observability proxy
    "AgentOps-AI/agentops",             # 5k   ★  agent monitoring SDK
    "EleutherAI/lm-evaluation-harness", # 12k  ★  LLM evaluation framework
    "guardrails-ai/guardrails",         # 6k   ★  LLM output validation
    "mlflow/mlflow",                    # 25k  ★  ML experiment tracking
    "wandb/wandb",                      # 11k  ★  ML observability platform
    # ── Agent Execution & Environments ───────────────────────────────────────
    "e2b-dev/E2B",                      # 11k  ★  secure execution environments
    "simular-ai/Agent-S",               # 10k  ★  computer-use agent framework
    "TencentQQGYLab/AppAgent",          # 6k   ★  smartphone app agent
    "GreyDGL/PentestGPT",               # 12k  ★  pentest agent framework
    "InternLM/MindSearch",              # 6k   ★  web search agent
    "SerpentAI/SerpentAI",              # 6k   ★  game agent framework
    "HKUDS/AutoAgent",                  # 9k   ★  LLM agent framework
    "browser-use/browser-use",          # 90k  ★  browser automation for agents
    # ── ML/AI Infrastructure ──────────────────────────────────────────────────
    "ml-explore/mlx",                   # 25k  ★  Apple Silicon ML framework
    "NVIDIA-NeMo/NeMo",                 # 17k  ★  NVIDIA conversational AI
    "huggingface/peft",                 # 21k  ★  parameter-efficient fine-tuning
    "huggingface/accelerate",           # 9k   ★  distributed training
    "OpenPipe/OpenPipe",                # 2k   ★  LLM fine-tuning platform
    "VoltAgent/voltagent",              # 8k   ★  TypeScript agent framework
]

# ---------------------------------------------------------------------------
# GitHub metadata
# ---------------------------------------------------------------------------

def get_repo_meta(full_name: str) -> dict | None:
    url = f"{BASE}/repos/{full_name}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as exc:
        print(f"    network error for {full_name}: {exc}", file=sys.stderr)
        return None
    if r.status_code == 200:
        return r.json()
    if r.status_code in (403, 429):
        reset = r.headers.get("X-RateLimit-Reset", "?")
        print(f"    rate-limited (reset={reset}): {full_name}", file=sys.stderr)
    elif r.status_code != 404:
        print(f"    HTTP {r.status_code}: {full_name}", file=sys.stderr)
    return None

# ---------------------------------------------------------------------------
# Grade
# ---------------------------------------------------------------------------

def grade(score: float) -> str:
    if score >= 80: return "S"
    if score >= 65: return "A"
    if score >= 50: return "B"
    if score >= 35: return "C"
    if score >= 20: return "D"
    return "F"

# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def scan_repo(full_name: str) -> dict | None:
    owner, repo_name = full_name.split("/", 1)
    print(f"  → {full_name}", flush=True)

    # 1. Fetch GitHub metadata
    meta = get_repo_meta(full_name)
    if not meta:
        print(f"    ✗ {full_name}: could not fetch metadata", file=sys.stderr)
        return None

    # 2. Shallow clone into a temp directory
    tmpdir = tempfile.mkdtemp(prefix="ar_scan_")
    try:
        clone_url = f"https://github.com/{full_name}.git"
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", "--no-tags",
             clone_url, tmpdir],
            capture_output=True,
            timeout=120,
        )
        if clone.returncode != 0:
            err = clone.stderr.decode(errors="replace")[:300]
            print(f"    ✗ {full_name}: clone failed: {err}", file=sys.stderr)
            return None

        # 3. Run agent-readiness scan
        ar = subprocess.run(
            ["agent-readiness", "scan", tmpdir, "--json"],
            capture_output=True,
            timeout=120,
        )
        stdout = ar.stdout.decode(errors="replace").strip()

        # agent-readiness exits 1 when findings are present — that's still valid output
        if not stdout:
            err = ar.stderr.decode(errors="replace")[:300]
            print(f"    ✗ {full_name}: no output from agent-readiness: {err}", file=sys.stderr)
            return None

        # 4. Parse JSON output
        try:
            ar_data = json.loads(stdout)
        except json.JSONDecodeError as exc:
            print(f"    ✗ {full_name}: JSON parse error: {exc}", file=sys.stderr)
            return None

        # 5. Extract pillar scores and top findings.
        #
        # Findings are grouped by check_id so any check that fires more than
        # once folds into a single summary row. Without this, verbose checks
        # like repo_shape.large_files (one finding per oversized file) crowd
        # out diverse signals such as headless.no_setup_prompts or
        # git.churn_hotspots — empirically ~80% of all top-findings entries
        # were large-file rows before this change.
        overall_score = round(float(ar_data.get("overall_score", 0.0)), 1)
        pillars: dict[str, float] = {}
        groups: dict[str, dict] = {}

        for pillar_obj in ar_data.get("pillars", []):
            pname = pillar_obj.get("pillar", "")
            pillars[pname] = round(float(pillar_obj.get("score", 0.0)), 1)

            for check in pillar_obj.get("checks", []):
                cid = check.get("check_id", "")
                for finding in check.get("findings", []):
                    sev = finding.get("severity", "")
                    hint = finding.get("fix_hint", "")
                    if sev not in ("warn", "error") or not hint:
                        continue
                    g = groups.setdefault(cid, {
                        "pillar":   pname,
                        "check_id": cid,
                        "severity": sev,
                        "fix_hint": hint,
                        "raw":      [],
                    })
                    g["raw"].append(finding.get("message", ""))
                    # Worst severity wins for the group.
                    if sev == "error":
                        g["severity"] = "error"

        # Materialise one summary finding per check_id.
        top_findings: list[dict] = []
        for g in groups.values():
            n = len(g["raw"])
            if n == 1:
                msg = g["raw"][0]
            else:
                sample = "; ".join(g["raw"][:2])
                msg = f"{n} findings — e.g. {sample}"
            top_findings.append({
                "pillar":   g["pillar"],
                "check_id": g["check_id"],
                "message":  msg,
                "severity": g["severity"],
                "fix_hint": g["fix_hint"],
                "count":    n,
            })

        # Errors first, then warn; within a severity bucket, larger
        # groups float up so the user sees the biggest concentrations
        # first. Cap at 8 distinct check_ids.
        top_findings.sort(key=lambda f: (
            0 if f["severity"] == "error" else 1,
            -f["count"],
            f["pillar"],
        ))
        top_findings = top_findings[:8]

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return {
        "repo":          full_name,
        "name":          meta["name"],
        "owner":         owner,
        "description":   meta.get("description") or "",
        "stars":         meta.get("stargazers_count", 0),
        "forks":         meta.get("forks_count", 0),
        "language":      meta.get("language") or "",
        "url":           meta["html_url"],
        "avatar":        meta["owner"]["avatar_url"],
        "topics":        (meta.get("topics") or [])[:6],
        "overall_score": overall_score,
        "grade":         grade(overall_score),
        "pillars":       pillars,
        "top_findings":  top_findings,
        "scanned_at":    datetime.now(timezone.utc).isoformat(),
    }

# ---------------------------------------------------------------------------
# Target list helpers
# ---------------------------------------------------------------------------

def _load_experiment_repo_names(path: str | os.PathLike[str]) -> list[str]:
    p = Path(path)
    if not p.is_file():
        return []
    try:
        doc = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    repos = doc.get("repos")
    if not isinstance(repos, list):
        return []
    return [str(x) for x in repos if x]


def resolve_scan_targets(
    *,
    curated_only: bool,
    experiment_only: bool,
    experiment_json: Path,
) -> list[str]:
    if experiment_only:
        names = _load_experiment_repo_names(experiment_json)
        if not names:
            print(f"No repos in {experiment_json} — run scripts/discover_repos.py first", file=sys.stderr)
        return names
    names = list(TARGET_REPOS)
    if curated_only:
        return names
    extra = _load_experiment_repo_names(experiment_json)
    seen = {n.lower() for n in names}
    for r in extra:
        if r.lower() not in seen:
            names.append(r)
            seen.add(r.lower())
    return names


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Shallow-clone and agent-readiness scan each target repo.")
    ap.add_argument(
        "--output",
        "-o",
        type=Path,
        default=Path("data/scores.json"),
        help="Write scores JSON here (default: data/scores.json).",
    )
    ap.add_argument(
        "--experiment-json",
        type=Path,
        default=Path("data/experiment_repos.json"),
        help="Pool file from discover_repos.py (default: data/experiment_repos.json).",
    )
    ap.add_argument(
        "--with-experiment",
        action="store_true",
        help="Scan curated TARGET_REPOS plus repos listed in --experiment-json.",
    )
    ap.add_argument(
        "--experiment-only",
        action="store_true",
        help="Scan only repos from --experiment-json (daily experiment pool).",
    )
    args = ap.parse_args()

    targets = resolve_scan_targets(
        curated_only=not args.with_experiment and not args.experiment_only,
        experiment_only=args.experiment_only,
        experiment_json=args.experiment_json,
    )
    if not targets:
        if args.experiment_only:
            out_path = args.output
            out_path.parent.mkdir(parents=True, exist_ok=True)
            empty = {
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "scan_version": "2.0.0",
                "scanner": "agent-readiness",
                "total_repos": 0,
                "repos": [],
                "scan_mode": "experiment_only",
            }
            out_path.write_text(json.dumps(empty, indent=2))
            print(f"No experiment repos — wrote empty scores → {out_path}")
            return 0
        return 1

    print("Agent Readiness Scanner v2.0")
    print("=" * 50)
    print(f"Repos to scan: {len(targets)}")

    results: list[dict] = []
    failed:  list[str]  = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(scan_repo, name): name for name in targets}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                result = fut.result()
                if result:
                    results.append(result)
                else:
                    failed.append(name)
            except Exception as exc:
                print(f"    ✗ {name}: unexpected error: {exc}", file=sys.stderr)
                failed.append(name)

    results.sort(key=lambda x: x["overall_score"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i

    output = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "scan_version": "2.0.0",
        "scanner":      "agent-readiness",
        "total_repos":  len(results),
        "repos":        results,
        "scan_mode": (
            "experiment_only"
            if args.experiment_only
            else ("curated_plus_experiment" if args.with_experiment else "curated_only")
        ),
    }

    out_path = args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Scanned {len(results)} repos → {out_path}")
    if failed:
        print(f"  ✗ Failed ({len(failed)}): {', '.join(failed)}")
    print()
    for r in results:
        filled = int(r["overall_score"] / 5)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"  #{r['rank']:3d} [{r['grade']}] {r['repo']:<45} {bar} {r['overall_score']:5.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
