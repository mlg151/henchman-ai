# AGENTS.md

## Stable architectural notes

- Canonical project-local config directory is `.henchman`; legacy casing is read-only fallback, not a write target.
- Discovery/help/doc truth should derive from the shared capability matrix in `src/henchman/cli/commands/discovery_capabilities.py`.
- Project-local agent catalog loading must ignore the `.henchman/agents/agents.json` persistence artifact.
- Tier 1 is foundations-first: stabilize baseline imports/tests before shared config plumbing, then CLI slices and tools.
- `config` command contract: `view`, `get`, `set`, `unset`, `import`, `export`.
- Guided upgrade flows must use argv-only safe execution and fall back to manual guidance when install detection is unknown or ambiguous.
- Local settings sync is file-based `import`/`export` only; no backend/cloud sync.
- Builtin tool exports are discoverable only when `src/henchman/tools/builtins/__init__.py` wires a real implementation via `import_path`; placeholder exports stay undiscoverable.

## Agent Development Guide

Use this file as the short operational guide for AI agents and human contributors working inside the repository. Treat [`HENCHMAN.md`](HENCHMAN.md) as the project context entrypoint, and treat [`.github/copilot-instructions.md`](.github/copilot-instructions.md) as the deeper, high-detail playbook.

## Workflow expectations

1. Read the roadmap item, nearby tests, and the closest reference docs before changing code.
2. Prefer TDD for behavior changes: add or update the failing test before implementing the change.
3. Keep edits scoped to the request; do not opportunistically refactor unrelated areas.
4. Preserve the canonical `.henchman/` path and avoid writing to legacy casing variants.
5. Update docs and changelog entries when a user-facing surface changes.

## Testing & quality gates

- Use focused verification for touched areas:
  - `uv run --extra dev python -m pytest --no-cov <target>`
  - `uv run --extra dev python -m ruff check <target>`
  - `uv run --extra dev python -m mypy <target>`
- Match repository conventions: type hints, concise docstrings, and no silent fallbacks for real errors.
- Prefer existing helpers and existing docs over inventing parallel patterns.

## File placement conventions

- Production code belongs under `src/henchman/`.
- Tests belong under `tests/`, ideally mirroring the module they cover.
- Long-form documentation belongs in `docs/`.
- Project context belongs in `HENCHMAN.md`.
- Roadmap state belongs in `FEATURE_TODO.md` and `TODOS.md`.

## Delegation & specialists

- Use research/planning/implementation specialist flows when the task naturally splits into discovery, design, and execution.
- Reach for focused exploration first, then implementation, then verification; do not keep re-reading the same files without making progress.
- Delegate documentation-heavy work by linking to existing source-of-truth docs instead of copying large blocks of content.

## Documentation updates

- When you add or change a surface area, update the nearest durable docs in the same task.
- Prefer linking to the canonical source (`docs/architecture.md`, `docs/api.md`, `docs/extensions.md`, `.github/copilot-instructions.md`) rather than duplicating long sections.
- Keep `TODOS.md` aligned with the current roadmap and record released doc work in `CHANGELOG.md`.
