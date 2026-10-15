"""Tests for Tier 6 Tungsten and auxiliary services."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.cli.tool_manager import ToolManager


def test_builtin_surface_includes_tungsten_tool() -> None:
    """The builtin surface should expose the Tier 6 Tungsten tool."""

    import henchman.tools.builtins as builtins_mod

    assert {"TungstenTool"} <= set(builtins_mod.__all__)

    def _instantiate(tool_class: object) -> object:
        if tool_class is builtins_mod.ShellTool:
            return builtins_mod.ShellTool(default_timeout=60)
        if tool_class is builtins_mod.RagSearchTool:
            from unittest.mock import MagicMock

            return builtins_mod.RagSearchTool(store=MagicMock())
        return tool_class()

    names = {_instantiate(tool_class).name for tool_class in builtins_mod.iter_available_builtin_tool_classes()}

    assert {"tungsten"} <= names


@pytest.mark.anyio
async def test_tungsten_tool_snapshots_and_compares_workspace_state(tmp_path: Path) -> None:
    """TungstenTool should snapshot and compare immutable workspace states."""

    from henchman.advanced import TungstenService

    tracked = tmp_path / "tracked.py"
    tracked.write_text("print('before')\n", encoding="utf-8")

    manager = ToolManager()
    manager.bind_runtime(project_root=tmp_path)
    manager.register_builtin_tools()

    first = await manager.registry.execute(
        "tungsten",
        {"action": "snapshot", "name": "before", "paths": ["tracked.py"]},
    )
    tracked.write_text("print('after')\n", encoding="utf-8")
    second = await manager.registry.execute(
        "tungsten",
        {"action": "snapshot", "name": "after", "paths": ["tracked.py"]},
    )

    assert first.success is True
    assert second.success is True

    service = TungstenService(project_root=tmp_path)
    snapshots = service.list_snapshots()
    compared = await manager.registry.execute(
        "tungsten",
        {
            "action": "compare",
            "left": snapshots[0].snapshot_id,
            "right": snapshots[1].snapshot_id,
        },
    )

    assert compared.success is True
    assert "modified: tracked.py" in compared.content
    assert (tmp_path / ".henchman" / "tungsten" / "snapshots.json").exists()


def test_auxiliary_tier6_services_produce_deterministic_outputs() -> None:
    """Auxiliary Tier 6 services should expose deterministic outputs."""

    from henchman.advanced import (
        AutoDreamService,
        MagicDocsService,
        PromptSuggestionService,
        TipsService,
    )

    dreams = AutoDreamService().generate(
        backlog=["MCP auth follow-up", "Schedule nightly verification"],
        recent_findings=["Tier 6 task runtime is complete."],
    )
    docs = MagicDocsService().render_feature_doc(
        title="Tier 6",
        summary="Advanced tooling is now available.",
        bullets=["Task runtime", "LSP service", "Cron scheduling"],
        references=["src/henchman/tools/builtins/tier6_tools.py"],
    )
    tips = TipsService().build_tips(
        active_tasks=["tier6-docs-status"],
        next_step="Update the roadmap and changelog.",
        disconnected_mcp=["filesystem"],
        paused_schedules=["nightly-check"],
    )
    prompts = PromptSuggestionService().suggest_next_prompts(
        active_tasks=["tier6-docs-status"],
        next_step="Update the roadmap and changelog.",
        missing_docs=["CHANGELOG.md"],
    )

    assert any("MCP auth follow-up" in dream for dream in dreams)
    assert "## Tier 6" in docs
    assert "Task runtime" in docs
    assert any("filesystem" in tip for tip in tips)
    assert any("CHANGELOG.md" in prompt for prompt in prompts)
