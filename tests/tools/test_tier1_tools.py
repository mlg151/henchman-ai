"""Focused tests for Tier 1 builtin tool discovery and invocation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from henchman.cli.tool_manager import ToolManager
from henchman.tools.base import Tool, ToolResult


class _AlphaTool(Tool):
    """Test helper tool with a searchable name."""

    @property
    def name(self) -> str:
        return "alpha_search"

    @property
    def description(self) -> str:
        return "Inspect alpha state."

    async def execute(self, **params: object) -> ToolResult:
        del params
        return ToolResult(content="alpha")


class _BetaTool(Tool):
    """Test helper tool with a searchable description."""

    @property
    def name(self) -> str:
        return "beta"

    @property
    def description(self) -> str:
        return "Searches by description text."

    async def execute(self, **params: object) -> ToolResult:
        del params
        return ToolResult(content="beta")


class _WebSearchTool(Tool):
    """Test helper that mirrors the runtime web search name."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for current information."

    async def execute(self, **params: object) -> ToolResult:
        del params
        return ToolResult(content="web")


class _ScheduleCronTool(Tool):
    """Test helper that mirrors the metadata-only schedule surface."""

    @property
    def name(self) -> str:
        return "schedule_cron"

    @property
    def description(self) -> str:
        return "Persist cron schedule metadata only."

    async def execute(self, **params: object) -> ToolResult:
        del params
        return ToolResult(content="schedule")


class _DynamicKnowledgeTool(Tool):
    """Tool registered after builtin construction to model RAG/plugins."""

    @property
    def name(self) -> str:
        return "dynamic_knowledge"

    @property
    def description(self) -> str:
        return "Search dynamic knowledge registered at runtime."

    async def execute(self, **params: object) -> ToolResult:
        del params
        return ToolResult(content="dynamic")


class TestToolSearchTool:
    """Tests for Tier 1 tool search behavior."""

    @pytest.mark.anyio
    async def test_tool_search_matches_name_and_description(self) -> None:
        """Tool search finds tools through shared metadata."""
        from henchman.tools.builtins.tier1_tools import ToolSearchTool

        tool = ToolSearchTool(tool_class_resolver=lambda: (_AlphaTool, _BetaTool))

        by_name = await tool.execute(query="alpha")
        by_description = await tool.execute(query="description text")

        assert by_name.success is True
        assert "- alpha_search: Inspect alpha state." in by_name.content
        assert by_description.success is True
        assert "- beta: Searches by description text." in by_description.content

    @pytest.mark.anyio
    async def test_tool_search_reports_no_matches(self) -> None:
        """Tool search returns actionable guidance when nothing matches."""
        from henchman.tools.builtins.tier1_tools import ToolSearchTool

        tool = ToolSearchTool(tool_class_resolver=lambda: (_AlphaTool,))

        result = await tool.execute(query="missing")

        assert result.success is False
        assert 'No tools or capability classifications matched "missing".' in result.content

    @pytest.mark.anyio
    async def test_tool_search_renders_capability_classifications(self) -> None:
        """Tool search should classify runtime and narrowed surfaces truthfully."""
        from henchman.tools.builtins.tier1_tools import ToolSearchTool

        tool = ToolSearchTool(
            tool_class_resolver=lambda: (_WebSearchTool, _ScheduleCronTool),
        )

        result = await tool.execute(limit=100)

        assert result.success is True
        assert (
            "- web_search [runtime-wired]: Search the web for current information."
            in result.content
        )
        assert (
            "- schedule_cron [metadata-only]: Persist cron schedule metadata only."
            in result.content
        )
        assert "Capability truth:" in result.content
        assert "- GitHub webhook-helper [docs-only]:" in result.content
        assert "- Tier 10 dialogs [undiscoverable]:" in result.content

    @pytest.mark.anyio
    async def test_tool_search_finds_capability_only_surfaces(self) -> None:
        """Capability-only entries should still be searchable through tool_search."""
        from henchman.tools.builtins.tier1_tools import ToolSearchTool

        tool = ToolSearchTool(tool_class_resolver=lambda: (_AlphaTool,))

        result = await tool.execute(query="dialog")

        assert result.success is True
        assert "- Tier 10 dialogs [undiscoverable]:" in result.content
        assert "- alpha_search:" not in result.content

    @pytest.mark.anyio
    async def test_tool_search_finds_tools_registered_after_runtime_binding(
        self,
        tmp_path: Path,
    ) -> None:
        """Runtime discovery must include tools added after builtins."""

        manager = ToolManager()
        manager.bind_runtime(project_root=tmp_path)
        manager.register_builtin_tools()
        manager.registry.register(_DynamicKnowledgeTool())

        result = await manager.registry.execute(
            "tool_search",
            {"query": "dynamic knowledge"},
        )

        assert result.success is True
        assert (
            "- dynamic_knowledge: Search dynamic knowledge registered at runtime." in result.content
        )

    @pytest.mark.anyio
    async def test_tool_search_does_not_advertise_absent_dynamic_tools(
        self,
        tmp_path: Path,
    ) -> None:
        """A different runtime must not inherit dynamic registrations."""

        manager = ToolManager()
        manager.bind_runtime(project_root=tmp_path)
        manager.register_builtin_tools()

        result = await manager.registry.execute(
            "tool_search",
            {"query": "dynamic knowledge"},
        )

        assert result.success is False
        assert "dynamic_knowledge" not in result.content


class TestSkillTool:
    """Tests for local skill dispatch."""

    @pytest.mark.anyio
    async def test_skill_tool_dispatches_known_skill(self) -> None:
        """Skill invocations route through the local bundled handlers."""
        from henchman.tools.builtins.tier1_tools import SkillTool

        handler = AsyncMock(return_value=ToolResult(content="Ran planner skill."))
        tool = SkillTool(skill_handlers={"planner": handler})

        result = await tool.execute(skill="planner")

        assert result.success is True
        assert result.content == "Ran planner skill."
        handler.assert_awaited_once_with()

    @pytest.mark.anyio
    async def test_skill_tool_rejects_unknown_skill(self) -> None:
        """Unknown skills fail without expanding into marketplace scope."""
        from henchman.tools.builtins.tier1_tools import SkillTool

        tool = SkillTool(skill_handlers={"planner": AsyncMock()})

        result = await tool.execute(skill="unknown")

        assert result.success is False
        # The available-skills list includes both handler-backed and catalog-discovered
        # skills — only assert that the registered handler name appears.
        assert "planner" in result.content

    @pytest.mark.anyio
    async def test_skill_tool_discovers_compatible_project_skills(
        self,
        tmp_path: Path,
    ) -> None:
        """SkillTool should expose compatible project skill formats without manual handlers."""
        from henchman.skills import SkillCatalog
        from henchman.tools.builtins.tier1_tools import SkillTool

        skill_file = tmp_path / ".github" / "skills" / "linting" / "SKILL.md"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(
            """---
name: linting
description: Run the linter
---
# Linting

Use the repository lint commands.
""",
            encoding="utf-8",
        )

        tool = SkillTool(
            skill_catalog=SkillCatalog(project_root=tmp_path, home_dir=tmp_path / "home")
        )

        result = await tool.execute(skill="linting")

        assert result.success is True
        assert "Run the linter" in result.content
        assert "repository lint commands" in result.content


class TestSleepTool:
    """Tests for bounded sleep behavior."""

    @pytest.mark.anyio
    async def test_sleep_tool_waits_within_bounds(self) -> None:
        """Sleep tool uses the configured sleeper and reports deterministically."""
        from henchman.tools.builtins.tier1_tools import SleepTool

        sleeper = AsyncMock()
        tool = SleepTool(sleeper=sleeper, max_seconds=5.0)

        result = await tool.execute(seconds=1.5)

        assert result.success is True
        assert result.content == "Slept for 1.5 seconds."
        sleeper.assert_awaited_once_with(1.5)

    @pytest.mark.anyio
    async def test_sleep_tool_rejects_out_of_bounds_values(self) -> None:
        """Sleep tool rejects negative and overly long delays."""
        from henchman.tools.builtins.tier1_tools import SleepTool

        tool = SleepTool(max_seconds=5.0)

        negative = await tool.execute(seconds=-1)
        too_long = await tool.execute(seconds=10)

        assert negative.success is False
        assert "between 0.0 and 5.0 seconds" in negative.content
        assert too_long.success is False
        assert "between 0.0 and 5.0 seconds" in too_long.content


class TestWebSearchTool:
    """Tests for the concrete Tier 1 web search export."""

    @pytest.mark.anyio
    async def test_web_search_tool_reports_missing_dependencies(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Web search should keep explicit dependency remediation when unavailable."""
        from henchman.tools.builtins import web_search as web_search_module
        from henchman.tools.builtins.tier1_tools import WebSearchTool

        monkeypatch.setattr(web_search_module, "_DEPS_AVAILABLE", False)

        result = await WebSearchTool().execute(query="python")

        assert result.success is False
        assert "aiohttp and beautifulsoup4 are required for web_search" in result.content
        assert (
            result.error
            == "Dependencies not installed. Please run: pip install aiohttp beautifulsoup4"
        )

    @pytest.mark.anyio
    async def test_tool_manager_executes_concrete_web_search_tool(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """ToolManager should execute the real web search implementation."""
        from henchman.tools.builtins import web_search as web_search_module

        search = AsyncMock(return_value=ToolResult(content="### Result", success=True))
        monkeypatch.setattr(web_search_module, "_DEPS_AVAILABLE", True)
        monkeypatch.setattr(web_search_module, "_search_duckduckgo_results", search)

        manager = ToolManager()
        manager.register_builtin_tools()

        result = await manager.registry.execute(
            "web_search",
            {"query": "python", "max_results": 3},
        )

        assert result.success is True
        assert result.content == "### Result"
        search.assert_awaited_once_with("python", 3)


class TestTier1BuiltinExports:
    """Tests for Tier 1 builtin discovery surface."""

    def test_builtins_export_tier1_tools(self) -> None:
        """The builtin module exposes the full Tier 1 tool surface."""
        import henchman.tools.builtins as builtins_mod

        assert {"ToolSearchTool", "SkillTool", "SleepTool", "WebSearchTool"} <= set(
            builtins_mod.__all__
        )

    def test_tool_manager_registers_tier1_tools(self) -> None:
        """Tool manager discovers the new Tier 1 tools through builtin exports."""
        tools = ToolManager._create_builtin_tools(shell_timeout=60)

        names = {tool.name for tool in tools}

        assert {"tool_search", "skill", "sleep", "web_search"} <= names

    @pytest.mark.anyio
    async def test_tool_manager_binds_runtime_skill_catalog(
        self,
        tmp_path: Path,
    ) -> None:
        """Tool manager should bind project-root skill discovery into the builtin skill tool."""
        skill_file = tmp_path / ".henchman" / "skills" / "deploy.yaml"
        skill_file.parent.mkdir(parents=True, exist_ok=True)
        skill_file.write_text(
            """name: deploy
description: Deploy the service
steps:
  - Run tests
""",
            encoding="utf-8",
        )

        manager = ToolManager()
        manager.bind_runtime(project_root=tmp_path)
        manager.register_builtin_tools()

        result = await manager.registry.execute("skill", {"skill": "deploy"})

        assert result.success is True
        assert "Deploy the service" in result.content

    def test_iter_available_builtin_tools_includes_web_search_and_new_tools(self) -> None:
        """Builtin iteration keeps WebSearchTool aligned with the new Tier 1 exports."""
        import henchman.tools.builtins as builtins_mod

        def _instantiate(tool_class: object) -> object:
            if tool_class is builtins_mod.ShellTool:
                return builtins_mod.ShellTool(default_timeout=60)
            if tool_class is builtins_mod.RagSearchTool:
                from unittest.mock import MagicMock

                return builtins_mod.RagSearchTool(store=MagicMock())
            return tool_class()

        names = {
            _instantiate(tool_class).name
            for tool_class in builtins_mod.iter_available_builtin_tool_classes()
        }

        assert {"tool_search", "skill", "sleep", "web_search"} <= names
