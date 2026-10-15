# HENCHMAN.md

This is the project-local context file for Henchman-AI. It gives agents and contributors a concise orientation to the codebase, the preferred workflow, and the fastest path to deeper reference material.

## Architecture Overview

Henchman-AI is a Python CLI for multi-provider, tool-using agents. The runtime is organized into focused subsystems:

- `src/henchman/cli/` - Click entrypoints, REPL wiring, command handling, Rich/Textual UI surfaces.
- `src/henchman/core/` - Agent loop, events, sessions, session export/import, and context state.
- `src/henchman/agents/` - Multi-agent orchestration, delegation, presets, catalogs, and platform management.
- `src/henchman/tools/` - Builtin tool interfaces, registry, security policy, and tiered tool surfaces.
- `src/henchman/providers/` - Model providers and the OpenAI-compatible abstraction.
- `src/henchman/config/` - Settings schema, repository-backed config, paths, and context loading.
- `src/henchman/mcp/` - Model Context Protocol configuration, auth, clients, and managers.
- `src/henchman/api/`, `extensions/`, `integrations/`, `team/`, `ops/` - Remote APIs, plugin surfaces, integrations, collaboration, and operational services.

## Key directories

- `src/henchman/` - Production code.
- `tests/` - Test suite, usually mirroring `src/henchman/`.
- `docs/` - Long-form reference, guides, and tutorials.
- `.henchman/` - Canonical project-local settings and context directory.
- `.agent_tasks/` - Non-source task artifacts such as analysis notes or scratch scripts.
- `FEATURE_TODO.md` - Tiered roadmap source of truth.
- `TODOS.md` - Living snapshot of the current roadmap focus.

## Local model target

The included local model targets a 16 GB RAM laptop. CPU operation must remain
supported; GPU acceleration is optional. Validate model usefulness and total
application memory separately from weight-file size. See
[`FEATURE_TODO.md`](FEATURE_TODO.md#included-local-default-model).

## Runtime architecture

At runtime, the CLI entrypoint builds settings, loads project context from `HENCHMAN.md`, initializes tool and provider registries, and then routes work through either the headless CLI path or the interactive REPL. The REPL coordinates command execution, tool calls, session persistence, plugin loading, and multi-agent delegation without forcing any one subsystem to own the entire interaction loop.

For deeper structure, use:

- [`docs/architecture.md`](docs/architecture.md) for subsystem boundaries and component diagrams.
- [`docs/api.md`](docs/api.md) for public interfaces and major types.
- [`docs/index.md`](docs/index.md) for the docs landing page.

## Development Workflow

1. Read the relevant tests, roadmap items, and nearby docs before editing.
2. Use test-driven development for behavior changes: write or update the failing test first.
3. Keep changes surgical and consistent with the existing module boundaries.
4. Prefer focused verification over broad repository-wide reruns when unrelated baseline failures already exist.
5. Update user-facing docs, `FEATURE_TODO.md`, `TODOS.md`, and `CHANGELOG.md` when the surface area changes.

## Verification Commands

Use the project dev extras when running local verification:

- `uv run --extra dev python -m pytest --no-cov <target>`
- `uv run --extra dev python -m ruff check <target>`
- `uv run --extra dev python -m mypy <target>`

Common examples:

- `uv run --extra dev python -m pytest --no-cov tests/testing/test_tier9_documentation.py -q`
- `uv run --extra dev python -m ruff check tests/testing/test_tier9_documentation.py`
- `uv run --extra dev python -m mypy src/henchman/config/context.py`

## Deeper docs

- [`AGENTS.md`](AGENTS.md) - agent workflow expectations and development guardrails
- [`TODOS.md`](TODOS.md) - living roadmap snapshot
- [`.github/copilot-instructions.md`](.github/copilot-instructions.md) - deeper implementation and workflow guidance
- [`docs/index.md`](docs/index.md) - full documentation map
