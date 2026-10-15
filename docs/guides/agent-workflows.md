# Agent Workflows

This guide describes the preferred workflow for feature work inside Henchman-AI.

## Standard loop

1. Read the roadmap item and nearby tests.
2. Add or update the failing test first.
3. Implement the smallest complete change.
4. Run focused validation.
5. Update the docs and changelog for the changed surface.

## When to plan first

Use a planning step when the work spans multiple modules, introduces a new surface area, or changes behavior across CLI, config, and runtime layers.

## When to delegate

Split work into discovery, implementation, and verification when a task benefits from specialist focus. Keep the handoff small and point the specialist at the exact files or surfaces that matter.

## Related docs

- Repository root: `HENCHMAN.md`
- Repository root: `AGENTS.md`
- [First Session Tutorial](../tutorials/first-session.md)
