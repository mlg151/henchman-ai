"""Tier 9 documentation completion tests."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("relative_path", "required_sections"),
    [
        (
            "HENCHMAN.md",
            [
                "# HENCHMAN.md",
                "## Architecture Overview",
                "## Development Workflow",
                "## Verification Commands",
            ],
        ),
        (
            "AGENTS.md",
            [
                "# AGENTS.md",
                "## Stable architectural notes",
                "## Agent Development Guide",
                "## Delegation & specialists",
            ],
        ),
        (
            "TODOS.md",
            [
                "# TODOS.md",
                "## Completed tiers",
                "## Current focus",
                "Tier 10: UI (Textual Enhancements)",
            ],
        ),
    ],
)
def test_tier9_root_docs_exist_with_required_sections(
    relative_path: str, required_sections: list[str]
) -> None:
    """Tier 9 should ship the root documentation surfaces with stable headings."""
    doc_path = PROJECT_ROOT / relative_path

    assert doc_path.exists(), f"{relative_path} should exist for Tier 9"

    content = doc_path.read_text(encoding="utf-8")

    for section in required_sections:
        assert section in content, f"{relative_path} should include section: {section}"


@pytest.mark.parametrize(
    "relative_path",
    [
        "docs/index.md",
        "docs/getting-started.md",
        "docs/configuration.md",
        "docs/api.md",
        "docs/tools.md",
        "docs/providers.md",
        "docs/mcp.md",
        "docs/extensions.md",
    ],
)
def test_tier9_readme_documentation_links_resolve(relative_path: str) -> None:
    """Every docs page linked from the README should exist."""
    assert (PROJECT_ROOT / relative_path).exists(), f"Missing README-linked doc: {relative_path}"


def test_tier9_docs_directory_includes_guides_and_tutorials() -> None:
    """Tier 9 should expand docs with guide and tutorial collections."""
    guides = sorted((PROJECT_ROOT / "docs" / "guides").glob("*.md"))
    tutorials = sorted((PROJECT_ROOT / "docs" / "tutorials").glob("*.md"))

    assert guides, "docs/guides should contain at least one markdown guide"
    assert tutorials, "docs/tutorials should contain at least one markdown tutorial"


def test_tier9_feature_todo_is_marked_complete() -> None:
    """Tier 9 roadmap items should be checked off once the documentation lands."""
    content = (PROJECT_ROOT / "FEATURE_TODO.md").read_text(encoding="utf-8")

    expected_lines = [
        "Completed: `HENCHMAN.md`, expanded `AGENTS.md`, `TODOS.md`, and an expanded docs directory with API reference, tutorials, and guides.",
        "- [x] `CLAUDE.md` equivalent — architecture overview",
        "- [x] `AGENTS.md` equivalent — agent development guide",
        "- [x] `TODOS.md` — living TODO list",
        "- [x] Expanded docs directory (API reference, tutorials, guides)",
    ]

    for line in expected_lines:
        assert line in content
