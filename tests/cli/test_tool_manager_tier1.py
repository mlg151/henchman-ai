"""Focused tests for Tier 1 builtin tool registration."""

from pathlib import Path

import pytest

from henchman.cli.tool_manager import ToolManager


class TestBuiltinToolSurface:
    """Tests for resilient builtin exports."""

    def test_builtin_module_exposes_required_tier1_surface(self) -> None:
        """Builtin exports stay discoverable through the shared surface."""
        import henchman.tools.builtins as builtins_mod

        expected_exports = {
            "AskUserTool",
            "CodeFormatTool",
            "CoverageMapTool",
            "DeadCodeTool",
            "DeepResearchTool",
            "DelegateTaskTool",
            "DiffViewTool",
            "EditFileTool",
            "EnvInspectTool",
            "FileOverviewTool",
            "GitOpsTool",
            "GlobTool",
            "GrepTool",
            "ImportGraphTool",
            "KgQueryTool",
            "KgUpdateTool",
            "LintCheckTool",
            "LsTool",
            "PatchApplyTool",
            "PatternSearchTool",
            "PipInspectTool",
            "PytestRunTool",
            "PythonAstTool",
            "PythonExecTool",
            "RagSearchTool",
            "ReadFileTool",
            "ResearchNotesTool",
            "ShellTool",
            "SymbolTraceTool",
            "TestGenTool",
            "TracebackParseTool",
            "WebFetchTool",
            "WebSearchTool",
            "WriteFileTool",
        }

        assert expected_exports.issubset(set(builtins_mod.__all__))
        assert builtins_mod.WebSearchTool.__name__ == "DuckDuckGoSearchTool"
        assert builtins_mod.ShellTool().name == "shell"
        assert builtins_mod.WebSearchTool().name == "web_search"
        assert expected_exports.isdisjoint(set(builtins_mod.unavailable_builtin_exports()))

    def test_placeholder_exports_do_not_mask_required_tier1_tools(self) -> None:
        """Lazy compatibility exports must still expose required builtin tools."""
        import henchman.tools.builtins as builtins_mod

        builtin_names = {
            (
                builtins_mod.ShellTool(default_timeout=60)
                if tool_class is builtins_mod.ShellTool
                else tool_class()
            ).name
            for tool_class in builtins_mod.iter_available_builtin_tool_classes()
        }

        assert {
            "deep_research",
            "delegate_task",
            "file_overview",
            "pattern_search",
            "read_file",
            "research_notes",
            "shell",
            "symbol_trace",
            "web_fetch",
            "web_search",
            "write_file",
        } <= builtin_names

    def test_export_surface_keeps_rag_search_without_safe_default_instantiation(self) -> None:
        """RAG search should stay exported even though runtime wiring creates it separately."""
        import henchman.tools.builtins as builtins_mod

        assert "RagSearchTool" in builtins_mod.__all__
        assert builtins_mod.RagSearchTool not in builtins_mod.iter_available_builtin_tool_classes()  # type: ignore[attr-defined]
        assert "RagSearchTool" not in builtins_mod.unavailable_builtin_exports()

    def test_reported_regression_tools_use_concrete_exports(self) -> None:
        """Reported TUI regressions should resolve to real builtin implementations."""
        import henchman.tools.builtins as builtins_mod

        tools = {tool.name: tool for tool in ToolManager._create_builtin_tools(shell_timeout=60)}
        ask_user_tool_class = builtins_mod.AskUserTool  # type: ignore[attr-defined]
        git_ops_tool_class = builtins_mod.GitOpsTool  # type: ignore[attr-defined]
        ls_tool_class = builtins_mod.LsTool  # type: ignore[attr-defined]

        assert tools["ask_user"].__class__ is ask_user_tool_class
        assert tools["git_ops"].__class__ is git_ops_tool_class
        assert tools["ls"].__class__ is ls_tool_class
        assert {"AskUserTool", "GitOpsTool", "LsTool"}.isdisjoint(
            set(builtins_mod.unavailable_builtin_exports())
        )

    def test_unavailable_builtin_exports_reports_placeholder_exports(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Placeholder exports should be reported and skipped during discovery."""
        import henchman.tools.builtins as builtins_mod

        placeholder = builtins_mod._create_placeholder_tool(
            builtins_mod._BuiltinSpec(
                export_name="SyntheticUnavailableTool",
                tool_name="synthetic_unavailable",
                description="Synthetic unavailable builtin",
            )
        )
        monkeypatch.setattr(
            builtins_mod,
            "SyntheticUnavailableTool",
            placeholder,
            raising=False,
        )
        monkeypatch.setattr(
            builtins_mod,
            "__all__",
            [*builtins_mod.__all__, "SyntheticUnavailableTool"],
        )

        assert "SyntheticUnavailableTool" in builtins_mod.unavailable_builtin_exports()
        assert placeholder not in builtins_mod.iter_available_builtin_tool_classes()

    def test_tool_manager_creates_required_builtin_tools(self) -> None:
        """Tool manager instantiates the required Tier 1 builtin surface."""
        tools = ToolManager._create_builtin_tools(shell_timeout=60)
        names = {tool.name for tool in tools}

        assert names >= {
            "ask_user",
            "code_format",
            "coverage_map",
            "dead_code",
            "deep_research",
            "delegate_task",
            "diff_view",
            "edit_file",
            "env_inspect",
            "file_overview",
            "git_ops",
            "glob",
            "grep",
            "import_graph",
            "kg_query",
            "kg_update",
            "lint_check",
            "ls",
            "patch_apply",
            "pattern_search",
            "pip_inspect",
            "pytest_run",
            "python_ast",
            "python_exec",
            "read_file",
            "research_notes",
            "shell",
            "symbol_trace",
            "test_gen",
            "traceback_parse",
            "web_fetch",
            "web_search",
            "write_file",
        }

    @pytest.mark.asyncio
    async def test_tool_manager_executes_legacy_read_file_with_real_builtin(
        self,
        tmp_path: Path,
    ) -> None:
        """Tool manager should register concrete legacy builtins when they exist."""
        readme = tmp_path / "README.md"
        readme.write_text("legacy builtin content", encoding="utf-8")

        manager = ToolManager()
        manager.register_builtin_tools()

        result = await manager.registry.execute("read_file", {"path": str(readme)})

        assert result.success is True
        assert result.content == "legacy builtin content"
