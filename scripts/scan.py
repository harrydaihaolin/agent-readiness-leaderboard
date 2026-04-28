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
    "langchain-ai/langchain",
    "microsoft/semantic-kernel",
    "microsoft/autogen",
    "sgl-project/sglang",
    "vllm-project/vllm",
    "kubernetes/kubernetes",
    "ray-project/ray",
    "apache/airflow",
    "temporalio/temporal",
    "langfuse/langfuse",
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
