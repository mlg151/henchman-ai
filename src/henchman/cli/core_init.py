"""Core component initialization for Henchman-AI.

This module provides shared initialization logic for both REPL and Textual TUI.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from henchman.agents.orchestrator import Orchestrator
from henchman.cli.plugins import PluginManager
from henchman.cli.session_manager import ReplSessionManager
from henchman.cli.tool_manager import ToolManager
from henchman.core.eventbus import EventBus
from henchman.mcp.manager import McpManager

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from henchman.cli.tool_executor import ToolExecutor
    from henchman.config.schema import Settings
    from henchman.core.agent import Agent
    from henchman.providers.base import ModelProvider
    from henchman.tools.registry import ToolRegistry


@dataclass
class CoreContext:
    """Core components shared between UI implementations.

    Attributes:
        provider: Model provider for LLM interactions.
        tool_manager: Tool manager for tool registration and execution.
        tool_registry: Tool registry (alias to tool_manager.registry).
        mcp_manager: MCP manager for external tool servers.
        plugin_manager: Plugin manager for extensions.
        event_bus: Event bus for agent communication.
        orchestrator: Main orchestrator with agent pool.
        agent: Primary agent (Tech Lead from orchestrator).
        session_manager: Session management for conversation history.
        tool_executor: Tool execution handler.
        settings: Application settings.
        background_tasks: Set of background asyncio tasks for shutdown management.
    """

    provider: ModelProvider
    tool_manager: ToolManager
    tool_registry: ToolRegistry  # Alias for backwards compatibility
    mcp_manager: McpManager | None
    plugin_manager: PluginManager
    event_bus: EventBus
    orchestrator: Orchestrator
    agent: Agent
    session_manager: ReplSessionManager
    tool_executor: ToolExecutor | None = None  # UI-specific, initialized separately
    settings: Settings | None = None
    background_tasks: set[asyncio.Task[Any]] = field(default_factory=set)


def create_core_context(
    provider: ModelProvider,
    system_prompt: str = "",
    environment_context: str | None = None,
    settings: Settings | None = None,
    *,
    auto_approve_tools: bool = False,
    question_handler: Callable[[str], Awaitable[str | None]] | None = None,
) -> CoreContext:
    """Create core components shared between UI implementations.

    This function initializes the UI-agnostic components that both
    REPL and Textual TUI need to function.

    Args:
        provider: Model provider for LLM interactions.
        system_prompt: System prompt for the agent.
        environment_context: Pre-formatted environment block for agents.
        settings: Application settings.
        auto_approve_tools: Auto-approve all tool executions.
        question_handler: Optional UI channel for actual user answers.

    Returns:
        Initialized CoreContext with all core components.
    """
    # Initialize MCP manager if servers are configured
    mcp_manager: McpManager | None = None
    if settings and settings.mcp_servers:
        mcp_logging = settings.ui.mcp_logging if settings and settings.ui else False
        mcp_manager = McpManager.create_from_settings(settings, mcp_logging_enabled=mcp_logging)

    # Runtime dependencies must exist before builtins are registered so every
    # tool's bind_runtime hook receives the live objects it will use.
    session_manager = ReplSessionManager(auto_save=True)
    tool_manager = ToolManager(settings=settings, question_handler=question_handler)
    tool_manager.set_auto_approve(auto_approve=auto_approve_tools)
    tool_manager.bind_runtime(
        project_root=Path.cwd(),
        session_manager=session_manager,
        mcp_manager=mcp_manager,
    )
    tool_manager.register_builtin_tools()
    tool_registry = tool_manager.registry  # Backwards compatibility

    # Initialize Plugin Manager
    plugin_manager = PluginManager(None)  # UI instance set by caller
    plugin_manager.load_plugins_from_directory(Path.home() / ".henchman" / "plugins")
    # Also load from workspace plugins
    plugin_manager.load_plugins_from_directory(Path.cwd() / ".henchman" / "plugins")

    # Initialize EventBus
    event_bus = EventBus()

    # Initialize Orchestrator
    orchestrator = Orchestrator(
        default_provider=provider,
        tool_registry=tool_registry,
        event_bus=event_bus,
        settings=settings,
        system_prompt=system_prompt,
        environment_context=environment_context,
    )

    # Reference Tech Lead as primary agent
    agent = orchestrator.tech_lead

    return CoreContext(
        provider=provider,
        tool_manager=tool_manager,
        tool_registry=tool_registry,
        mcp_manager=mcp_manager,
        plugin_manager=plugin_manager,
        event_bus=event_bus,
        orchestrator=orchestrator,
        agent=agent,
        session_manager=session_manager,
        settings=settings,
    )


def initialize_mcp(context: CoreContext) -> None:
    """Initialize MCP servers asynchronously.

    This should be called by the UI after core context creation.

    Args:
        context: Core context with MCP manager.

    Returns:
        None
    """
    if context.mcp_manager and not context.mcp_manager.clients:
        mcp_manager = context.mcp_manager  # Captured for closure typing

        async def connect_mcp() -> None:
            """Connect to MCP servers and register tools."""
            try:
                await mcp_manager.connect_all()
                # Register MCP tools with the tool registry
                for tool in mcp_manager.get_all_tools():
                    context.tool_registry.register(tool)
            except Exception as e:
                # Log error but don't crash
                print(f"Failed to connect to MCP servers: {e}")

        # Run in background and store reference for shutdown management
        task = asyncio.create_task(connect_mcp())
        context.background_tasks.add(task)
