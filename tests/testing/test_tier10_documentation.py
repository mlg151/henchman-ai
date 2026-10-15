"""Tier 10 roadmap and discovery truth tests."""

from __future__ import annotations

from pathlib import Path

from henchman.cli.commands.discovery_capabilities import build_discovery_capabilities

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_tier10_feature_todo_is_marked_complete() -> None:
    """Tier 10 roadmap items should be checked off once the TUI lands."""
    content = (PROJECT_ROOT / "FEATURE_TODO.md").read_text(encoding="utf-8")

    expected_lines = [
        "Completed: workspace tab with agent/memory/task/skill/team/settings/context surfaces, status/progress affordances, permission prompts, and dialogs for search, history, theme, model, auto-mode, export, feedback, MCP, bridge, and onboarding.",
        "- [x] Agent summary panel",
        "- [x] Bridge dialog",
        "- [x] Context visualization",
        "- [x] Dev bar",
        "- [x] Export dialog",
        "- [x] Permissions dialogs",
        "- [x] Theme picker",
    ]

    for line in expected_lines:
        assert line in content


def test_tier10_docs_describe_implemented_but_undiscoverable_tui() -> None:
    """Root docs should describe Tier 10 as implemented in the TUI but undiscoverable generically."""
    todos = (PROJECT_ROOT / "TODOS.md").read_text(encoding="utf-8")

    assert "Tier 10 - Textual workspace UI" in todos
    assert "Textual dialogs are implemented in the TUI" in todos


def test_tier10_capability_matrix_stays_undiscoverable_but_shipped_in_tui() -> None:
    """The shared capability matrix should keep Tier 10 undiscoverable while acknowledging the TUI implementation."""
    capability = next(
        entry for entry in build_discovery_capabilities() if entry.name == "Tier 10 dialogs"
    )

    assert capability.classification == "undiscoverable"
    assert "ship in the TUI" in capability.summary
    assert "implemented inside `henchman chat --tui`" in capability.detail
