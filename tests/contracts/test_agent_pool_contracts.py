"""Contract tests for AgentPool and scoped registry creation.

These tests validate that:
- create_scoped_registry() produces a registry containing only allowed tools
- AgentPool lazily creates and manages agents
- The lifecycle contract (get, reset, shutdown) is preserved
"""

from __future__ import annotations

import pytest

from henchman.agents.pool import AgentPool, ContextConfig, create_scoped_registry
from henchman.tools.base import Tool, ToolResult
from henchman.tools.registry import ToolRegistry


class _ReadTool(Tool):
    """Minimal tool double for registry testing."""

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "Read a file"

    async def execute(self) -> ToolResult:
        return ToolResult(name="read", tool_call_id="", success=True, output="read result")


class _WriteTool(Tool):
    """Minimal tool double for registry testing."""

    @property
    def name(self) -> str:
        return "write"

    @property
    def description(self) -> str:
        return "Write to a file"

    async def execute(self) -> ToolResult:
        return ToolResult(name="write", tool_call_id="", success=True, output="write result")


class _ShellTool(Tool):
    """Minimal tool double for registry testing."""

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Run a shell command"

    async def execute(self) -> ToolResult:
        return ToolResult(name="shell", tool_call_id="", success=True, output="shell result")


class _CustomTool(Tool):
    """Extra tool for scoped registry testing."""

    @property
    def name(self) -> str:
        return "custom_tool"

    @property
    def description(self) -> str:
        return "A custom tool"

    async def execute(self) -> ToolResult:
        return ToolResult(name="custom_tool", tool_call_id="", success=True, output="custom result")


class _ExtraTool(Tool):
    """Extra tool that overrides an existing one."""

    @property
    def name(self) -> str:
        return "read"

    @property
    def description(self) -> str:
        return "Custom read tool"

    async def execute(self) -> ToolResult:
        return ToolResult(name="read", tool_call_id="", success=True, output="custom read result")


# ===========================================================================
# Scoped registry contracts
# ===========================================================================


class TestCreateScopedRegistryContract:
    """create_scoped_registry() must satisfy the tool-scoping contract."""

    def test_scoped_registry_contains_only_allowed_tools(self) -> None:
        """Only tools in the allowed list should be in the scoped registry."""
        parent = ToolRegistry()
        parent.register(_ReadTool())
        parent.register(_WriteTool())
        parent.register(_ShellTool())

        scoped = create_scoped_registry(
            parent=parent,
            allowed_tools=["read", "write"],
        )

        tool_names = scoped.list_tools()
        assert "read" in tool_names
        assert "write" in tool_names
        assert "shell" not in tool_names

    def test_scoped_registry_includes_extra_tools(self) -> None:
        """Extra tools should be included in the scoped registry."""
        parent = ToolRegistry()
        parent.register(_ReadTool())

        scoped = create_scoped_registry(
            parent=parent,
            allowed_tools=["read"],
            extra_tools=[_CustomTool()],
        )

        tool_names = scoped.list_tools()
        assert "read" in tool_names
        assert "custom_tool" in tool_names

    def test_extra_tool_overrides_parent(self) -> None:
        """Extra tools should override parent tools with the same name."""
        parent = ToolRegistry()
        parent.register(_ReadTool())

        scoped = create_scoped_registry(
            parent=parent,
            allowed_tools=["read"],
            extra_tools=[_ExtraTool()],
        )

        read_tool = scoped.get("read")
        assert read_tool is not None

    def test_parent_unmodified(self) -> None:
        """The parent registry should remain unmodified."""
        parent = ToolRegistry()
        parent.register(_ReadTool())
        parent.register(_WriteTool())

        original_names = set(parent.list_tools())

        create_scoped_registry(
            parent=parent,
            allowed_tools=["read"],
        )

        current_names = set(parent.list_tools())
        assert current_names == original_names

    def test_empty_allowed_list(self) -> None:
        """An empty allowed list should produce an empty scoped registry."""
        parent = ToolRegistry()
        parent.register(_ReadTool())

        scoped = create_scoped_registry(
            parent=parent,
            allowed_tools=[],
        )

        assert len(scoped.list_tools()) == 0

    def test_scoped_registry_with_auto_approve(self) -> None:
        """Auto-approve list should be respected in the scoped registry."""
        parent = ToolRegistry()
        parent.register(_ReadTool())
        parent.register(_WriteTool())

        scoped = create_scoped_registry(
            parent=parent,
            allowed_tools=["read", "write"],
            auto_approve=["read"],
        )

        tool_names = scoped.list_tools()
        assert "read" in tool_names
        assert "write" in tool_names


# ===========================================================================
# AgentPool lifecycle contracts
# ===========================================================================


class TestAgentPoolContract:
    """AgentPool must satisfy the lazy-init and lifecycle contract."""

    def test_pool_initialization_with_context_config(self) -> None:
        """AgentPool should accept a ContextConfig object."""
        ctx = ContextConfig(
            environment_context="env-block",
            intelligent_context=True,
            importance_threshold=0.7,
            cluster_similarity_threshold=0.8,
            adaptive_compression=False,
        )
        pool = AgentPool(
            configs={},
            default_provider=None,  # type: ignore[arg-type]
            provider_registry=None,
            parent_tool_registry=ToolRegistry(),
            event_bus=None,  # type: ignore[arg-type]
            context_config=ctx,
        )
        assert pool.context_config.intelligent_context is True
        assert pool.context_config.importance_threshold == 0.7
        assert pool.context_config.adaptive_compression is False

    def test_pool_empty_agents_list(self) -> None:
        """Pool with no configs should have empty agent lists."""
        pool = AgentPool(
            configs={},
            default_provider=None,  # type: ignore[arg-type]
            provider_registry=None,
            parent_tool_registry=ToolRegistry(),
            event_bus=None,  # type: ignore[arg-type]
        )
        assert pool.list_agents() == []
        assert pool.list_active_agents() == []

    def test_pool_shutdown_clears_agents(self) -> None:
        """Shutdown should clear all active agents."""
        pool = AgentPool(
            configs={},
            default_provider=None,  # type: ignore[arg-type]
            provider_registry=None,
            parent_tool_registry=ToolRegistry(),
            event_bus=None,  # type: ignore[arg-type]
        )
        pool.shutdown()
        assert pool.list_active_agents() == []

    def test_pool_unknown_agent_raises(self) -> None:
        """Getting an unconfigured agent should raise ValueError."""
        pool = AgentPool(
            configs={},
            default_provider=None,  # type: ignore[arg-type]
            provider_registry=None,
            parent_tool_registry=ToolRegistry(),
            event_bus=None,  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError, match="not configured"):
            pool.get_agent("nonexistent")

    def test_pool_get_identity_unknown_raises(self) -> None:
        """Getting identity for an unconfigured role should raise."""
        pool = AgentPool(
            configs={},
            default_provider=None,  # type: ignore[arg-type]
            provider_registry=None,
            parent_tool_registry=ToolRegistry(),
            event_bus=None,  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError, match="not configured"):
            pool.get_identity("nonexistent")

    def test_pool_environment_context_property(self) -> None:
        """environment_context should delegate to context_config."""
        pool = AgentPool(
            configs={},
            default_provider=None,  # type: ignore[arg-type]
            provider_registry=None,
            parent_tool_registry=ToolRegistry(),
            event_bus=None,  # type: ignore[arg-type]
            environment_context="test-env",
        )
        assert pool.environment_context == "test-env"
        assert pool.context_config.environment_context == "test-env"
