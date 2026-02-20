"""Component factory for REPL.

This module provides a factory for creating REPL components.
"""

from typing import TYPE_CHECKING

from henchman.cli.command_processor import CommandProcessor
from henchman.cli.input_handler import InputHandler
from henchman.cli.output_handler import OutputHandler
from henchman.cli.tool_executor import ToolExecutor
from henchman.cli.tool_manager import ToolManager
from henchman.core.eventbus import EventBus
from henchman.agents.orchestrator import Orchestrator

if TYPE_CHECKING:
    from pathlib import Path
    from henchman.cli.repl import ReplConfig
    from henchman.cli.ui_renderer import UIRenderer
    from henchman.config.schema import Settings
    from henchman.mcp.manager import McpManager
    from henchman.providers.base import ModelProvider


class ReplComponentFactory:
    """Factory for creating REPL components."""
    
    @staticmethod
    def create_components(
        provider: ModelProvider,
        config: ReplConfig,
        settings: Settings | None,
        renderer: UIRenderer,
        environment_context: str | None,
    ) -> dict:
        """Create all REPL components.
        
        Returns:
            Dictionary with component names as keys.
        """
        # Tool manager
        tool_manager = ToolManager(settings=settings)
        tool_manager.set_auto_approve(config.auto_approve_tools)
        tool_manager.register_builtin_tools()
        
        # MCP manager
        mcp_manager = None
        if settings and settings.mcp_servers:
            mcp_logging = settings.ui.mcp_logging if settings.ui else False
            from henchman.mcp.manager import McpManager
            mcp_manager = McpManager.create_from_settings(settings, mcp_logging)
        
        # Event bus and orchestrator
        event_bus = EventBus()
        orchestrator = Orchestrator(
            default_provider=provider,
            tool_registry=tool_manager.registry,
            event_bus=event_bus,
            settings=settings,
            system_prompt=config.system_prompt,
            environment_context=environment_context,
        )
        
        # Session manager
        from henchman.cli.session_manager import ReplSessionManager
        session_manager = ReplSessionManager(auto_save=config.auto_save)
        
        # Output handler
        output_handler = OutputHandler(
            renderer=renderer,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            settings=settings,
            rag_system=None,  # Set externally
            mcp_manager=mcp_manager,
        )
        
        # Command processor
        command_processor = CommandProcessor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            session_manager=session_manager,
            provider=provider,
            mcp_manager=mcp_manager,
        )
        
        # Tool executor
        tool_executor = ToolExecutor(
            output_handler=output_handler,
            tool_manager=tool_manager,
            provider=provider,
            base_tool_iterations=config.base_tool_iterations,
            max_tool_calls_per_turn=config.max_tool_calls_per_turn,
        )
        tool_manager.set_confirmation_handler(tool_executor.handle_confirmation)
        
        # Input handler
        from pathlib import Path
        history_file = config.history_file or Path.home() / ".henchman_history"
        input_handler = InputHandler(
            config=config,
            renderer=renderer,
            history_file=history_file
        )
        
        return {
            'tool_manager': tool_manager,
            'tool_registry': tool_manager.registry,
            'mcp_manager': mcp_manager,
            'event_bus': event_bus,
            'orchestrator': orchestrator,
            'session_manager': session_manager,
            'output_handler': output_handler,
            'command_processor': command_processor,
            'tool_executor': tool_executor,
            'input_handler': input_handler,
            'agent': orchestrator.tech_lead,  # Backwards compatibility
        }