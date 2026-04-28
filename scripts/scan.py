#!/usr/bin/env python3
"""
Agent Readiness Scanner
=======================
Scores AI agent infrastructure repos on how well they support AI agents
working within their own codebase.

Scoring dimensions (100 pts total):
  ai_context_files  25 pts  — CLAUDE.md, AGENTS.md, .cursorrules, etc.
  documentation     20 pts  — README, CONTRIBUTING, CHANGELOG, SECURITY
  testing           15 pts  — test dirs + runner configs
  ci_cd             15 pts  — GitHub Actions workflow count
  tooling           10 pts  — linting, formatting, type-checking
  code_structure    10 pts  — languages, topics, license
  conventions        5 pts  — issue/PR templates

Uses the Git Trees API (1 call per repo) instead of individual Content API
calls, keeping total API usage well within GitHub's rate limits.
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BASE = "https://api.github.com"

HEADERS: dict[str, str] = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "agent-readiness-leaderboard/1.0",
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
# HTTP helpers
# ---------------------------------------------------------------------------

def get(path: str) -> dict | list | None:
    url = path if path.startswith("http") else f"{BASE}{path}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as exc:
        print(f"    network error: {exc}", file=sys.stderr)
        return None
    if r.status_code == 200:
        return r.json()
    if r.status_code in (403, 429):
        reset = r.headers.get("X-RateLimit-Reset", "?")
        print(f"    rate-limited (reset={reset}): {url}", file=sys.stderr)
    elif r.status_code != 404:
        print(f"    HTTP {r.status_code}: {url}", file=sys.stderr)
    return None


def get_tree(owner: str, repo: str) -> set[str]:
    """Return all file paths in the repo via the recursive tree API."""
    data = get(f"/repos/{owner}/{repo}/git/trees/HEAD?recursive=1")
    if not data:
        return set()
    paths = {item["path"] for item in data.get("tree", []) if item.get("type") == "blob"}
    if data.get("truncated"):
        # Large repos: also pull the shallow root listing as fallback
        root = get(f"/repos/{owner}/{repo}/contents/")
        if isinstance(root, list):
            for item in root:
                paths.add(item["path"])
    return paths

# ---------------------------------------------------------------------------
# Scoring functions
# ---------------------------------------------------------------------------

def score_ai_context_files(tree: set[str]) -> dict:
    weighted = {
        "CLAUDE.md": 10,
        "AGENTS.md": 10,
        ".cursorrules": 8,
        "AI.md": 6,
        ".ai-context.md": 6,
        ".github/copilot-instructions.md": 5,
        "COPILOT.md": 4,
        "docs/AGENTS.md": 4,
        "CODEOWNERS": 2,
        ".github/CODEOWNERS": 2,
    }
    found = {f: pts for f, pts in weighted.items() if f in tree}
    score = min(sum(found.values()), 25)
    return {
        "score": score,
        "max": 25,
        "found": list(found.keys()),
        "detail": f"Found: {', '.join(found.keys())}" if found else "No AI context files detected",
    }


def score_documentation(tree: set[str], repo_data: dict) -> dict:
    score = 0
    found: list[str] = []
    if repo_data.get("description"):
        score += 2; found.append("description")
    if any(p in tree for p in ("README.md", "README.rst", "README")):
        score += 5; found.append("README")
    if any(p in tree for p in ("CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING")):
        score += 5; found.append("CONTRIBUTING")
    if "CODE_OF_CONDUCT.md" in tree:
        score += 2; found.append("CODE_OF_CONDUCT")
    if any(p in tree for p in ("CHANGELOG.md", "CHANGELOG", "CHANGELOG.rst", "HISTORY.md", "RELEASES.md")):
        score += 3; found.append("CHANGELOG")
    if "SECURITY.md" in tree:
        score += 3; found.append("SECURITY")
    return {
        "score": min(score, 20),
        "max": 20,
        "found": found,
        "detail": ", ".join(found) if found else "Minimal documentation",
    }


def score_testing(tree: set[str]) -> dict:
    test_dirs = ["__tests__", "tests", "test", "spec", "e2e", "cypress", "playwright", "integration_tests", "unit_tests"]
    test_configs = [
        "jest.config.js", "jest.config.ts", "jest.config.mjs",
        "pytest.ini", "setup.cfg", "conftest.py",
        ".mocharc.yml", ".mocharc.js",
        "vitest.config.ts", "vitest.config.js",
        "karma.conf.js",
        "cypress.config.js", "cypress.config.ts",
        "playwright.config.ts", "playwright.config.js",
        "phpunit.xml", "go.sum",
    ]
    found_dirs = [d for d in test_dirs if d in tree or any(p.startswith(d + "/") for p in tree)]
    found_cfgs = [c for c in test_configs if c in tree]
    score = min(len(found_dirs) * 4, 10) + min(len(found_cfgs) * 2, 5)
    found = found_dirs + found_cfgs
    return {
        "score": min(score, 15),
        "max": 15,
        "found": found,
        "detail": f"Dirs: {', '.join(found_dirs[:3])}; configs: {', '.join(found_cfgs[:3])}" if found else "No test infrastructure detected",
    }


def score_ci_cd(tree: set[str]) -> dict:
    workflows = [p for p in tree if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))]
    score = 0
    found: list[str] = []
    if workflows:
        score += 8; found.append(f"{len(workflows)} workflow(s)")
        if len(workflows) >= 4:
            score += 4
        if len(workflows) >= 8:
            score += 3
    if ".travis.yml" in tree:
        score += 2; found.append("Travis CI")
    if any(p in tree for p in ("Makefile", "Taskfile.yml", "Taskfile.yaml", "justfile")):
        score += 1; found.append("Makefile/Taskfile")
    return {
        "score": min(score, 15),
        "max": 15,
        "found": found,
        "workflow_count": len(workflows),
        "detail": ", ".join(found) if found else "No CI/CD configuration detected",
    }


def score_tooling(tree: set[str]) -> dict:
    tools: dict[str, int] = {
        ".eslintrc.js": 2, ".eslintrc.json": 2, ".eslintrc.yml": 2, ".eslintrc": 2,
        "eslint.config.js": 2, "eslint.config.mjs": 2,
        ".prettierrc": 2, ".prettierrc.json": 2, ".prettierrc.js": 2,
        ".editorconfig": 1,
        "pyproject.toml": 2, ".ruff.toml": 2, "ruff.toml": 2,
        ".flake8": 1, ".pylintrc": 1,
        "mypy.ini": 2, ".mypy.ini": 2,
        "tsconfig.json": 2,
        ".pre-commit-config.yaml": 2,
        "biome.json": 2,
        "lefthook.yml": 1,
        "renovate.json": 1, ".renovaterc": 1,
        "Dockerfile": 1,
    }
    found = {f: pts for f, pts in tools.items() if f in tree}
    score = min(sum(found.values()), 10)
    return {
        "score": score,
        "max": 10,
        "found": list(found.keys()),
        "detail": ", ".join(list(found.keys())[:5]) if found else "No tooling config detected",
    }


def score_code_structure(tree: set[str], repo_data: dict, languages: dict) -> dict:
    score = 0
    found: list[str] = []
    if languages:
        n = len(languages)
        score += min(n, 4); found.append(f"{n} language(s)")
    topics = repo_data.get("topics", [])
    if len(topics) >= 5:
        score += 3; found.append(f"{len(topics)} topics")
    elif len(topics) >= 2:
        score += 2; found.append(f"{len(topics)} topics")
    elif topics:
        score += 1
    if repo_data.get("license"):
        score += 3; found.append(repo_data["license"]["spdx_id"])
    return {
        "score": min(score, 10),
        "max": 10,
        "found": found,
        "detail": ", ".join(found) if found else "Minimal structure signals",
    }


def score_conventions(tree: set[str]) -> dict:
    score = 0
    found: list[str] = []
    issue_tmpls = [p for p in tree if p.startswith(".github/ISSUE_TEMPLATE/") or p == ".github/ISSUE_TEMPLATE.md"]
    if issue_tmpls:
        score += 2; found.append(f"{len(issue_tmpls)} issue template(s)")
    pr_tmpls = [
        p for p in tree if p in (
            ".github/PULL_REQUEST_TEMPLATE.md",
            ".github/pull_request_template.md",
        ) or p.startswith(".github/PULL_REQUEST_TEMPLATE/")
    ]
    if pr_tmpls:
        score += 2; found.append("PR template")
    if "GOVERNANCE.md" in tree:
        score += 1; found.append("GOVERNANCE.md")
    return {
        "score": min(score, 5),
        "max": 5,
        "found": found,
        "detail": ", ".join(found) if found else "No community conventions detected",
    }

# ---------------------------------------------------------------------------
# Grade
# ---------------------------------------------------------------------------

def grade(pct: float) -> str:
    if pct >= 90: return "S"
    if pct >= 80: return "A"
    if pct >= 70: return "B"
    if pct >= 55: return "C"
    if pct >= 40: return "D"
    return "F"

# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def scan_repo(full_name: str) -> dict | None:
    owner, repo = full_name.split("/", 1)
    print(f"  → {full_name}", flush=True)

    repo_data = get(f"/repos/{owner}/{repo}")
    if not repo_data or isinstance(repo_data, list):
        print(f"    ✗ could not fetch repo metadata", file=sys.stderr)
        return None

    tree = get_tree(owner, repo)
    languages: dict = get(f"/repos/{owner}/{repo}/languages") or {}

    categories = {
        "ai_context_files": score_ai_context_files(tree),
        "documentation":    score_documentation(tree, repo_data),
        "testing":          score_testing(tree),
        "ci_cd":            score_ci_cd(tree),
        "tooling":          score_tooling(tree),
        "code_structure":   score_code_structure(tree, repo_data, languages),
        "conventions":      score_conventions(tree),
    }

    total     = sum(c["score"] for c in categories.values())
    max_total = sum(c["max"]   for c in categories.values())
    pct       = round(total / max_total * 100, 1)

    return {
        "repo":        full_name,
        "name":        repo_data["name"],
        "owner":       owner,
        "description": repo_data.get("description") or "",
        "stars":       repo_data.get("stargazers_count", 0),
        "forks":       repo_data.get("forks_count", 0),
        "language":    repo_data.get("language") or "",
        "url":         repo_data["html_url"],
        "avatar":      repo_data["owner"]["avatar_url"],
        "topics":      (repo_data.get("topics") or [])[:6],
        "total_score": total,
        "max_score":   max_total,
        "percentage":  pct,
        "grade":       grade(pct),
        "categories":  categories,
        "scanned_at":  datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    print("Agent Readiness Scanner")
    print("=" * 50)

    results = []
    for name in TARGET_REPOS:
        result = scan_repo(name)
        if result:
            results.append(result)

    results.sort(key=lambda x: x["percentage"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i

    output = {
        "last_updated":  datetime.now(timezone.utc).isoformat(),
        "scan_version":  "1.0.0",
        "total_repos":   len(results),
        "repos":         results,
    }

    os.makedirs("data", exist_ok=True)
    with open("data/scores.json", "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✓ Scanned {len(results)} repos → data/scores.json\n")
    for r in results:
        filled = int(r["percentage"] / 5)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"  #{r['rank']:2d} [{r['grade']}] {r['repo']:<40} {bar} {r['percentage']:5.1f}%")


if __name__ == "__main__":
    main()
