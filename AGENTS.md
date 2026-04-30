# AGENTS.md

Coding agents working in this repo: read this first.

## Canonical commands

See `README.md` for project-specific install / build / test commands. Use them verbatim — do not invent new ones.

## Do not touch

- Generated files (`dist/`, `build/`, `data/` snapshots, vendored snapshots).
- Anything under `.git/`.
- Workspace-wide secrets (`.env*` files, `~/.gh/...`).

## House style

- One concern per PR; keep changes minimal and reviewable.
- Match the surrounding code's indentation, naming, and import order.
- Update tests when you change behaviour.
- Prefer additive changes (new function / module) over wholesale rewrites unless explicitly asked.

## Where to look

- `README.md` — human-facing overview, install, run.
- `CONTRIBUTING.md` — how to propose changes (if present).
- `SECURITY.md` — how to report vulnerabilities (if present).
