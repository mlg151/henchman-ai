"""Tests for core component initialization."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.core_init import CoreContext, create_core_context, initialize_mcp
from henchman.config.schema import ProviderSettings, Settings, ToolSettings, UISettings


class TestCoreContext:
    """Tests for CoreContext dataclass and initialization."""

    def test_core_context_creation(self):
        """Test that CoreContext can be created with all required fields."""
        # Create mock objects
        mock_provider = MagicMock()
        mock_tool_manager = MagicMock()
        mock_mcp_manager = MagicMock()
        mock_plugin_manager = MagicMock()
        mock_event_bus = MagicMock()
        mock_orchestrator = MagicMock()
        mock_agent = MagicMock()
        mock_session_manager = MagicMock()
        mock_tool_executor = MagicMock()
        mock_settings = MagicMock()

        # Create CoreContext
        context = CoreContext(
            provider=mock_provider,
            tool_manager=mock_tool_manager,
            tool_registry=mock_tool_manager,  # Alias
            mcp_manager=mock_mcp_manager,
            plugin_manager=mock_plugin_manager,
            event_bus=mock_event_bus,
            orchestrator=mock_orchestrator,
            agent=mock_agent,
            session_manager=mock_session_manager,
            tool_executor=mock_tool_executor,
            settings=mock_settings,
        )

        # Verify all fields are set
        assert context.provider == mock_provider
        assert context.tool_manager == mock_tool_manager
        assert context.tool_registry == mock_tool_manager
        assert context.mcp_manager == mock_mcp_manager
        assert context.plugin_manager == mock_plugin_manager
        assert context.event_bus == mock_event_bus
        assert context.orchestrator == mock_orchestrator
        assert context.agent == mock_agent
        assert context.session_manager == mock_session_manager
        assert context.tool_executor == mock_tool_executor
        assert context.settings == mock_settings

    def test_core_context_defaults(self):
        """Test that CoreContext can be created with optional fields as None."""
        # Create mock objects for required fields
        mock_provider = MagicMock()
        mock_tool_manager = MagicMock()
        mock_plugin_manager = MagicMock()
        mock_event_bus = MagicMock()
        mock_orchestrator = MagicMock()
        mock_agent = MagicMock()
        mock_session_manager = MagicMock()

        # Create CoreContext with optional fields as None
        context = CoreContext(
            provider=mock_provider,
            tool_manager=mock_tool_manager,
            tool_registry=mock_tool_manager,
            mcp_manager=None,
            plugin_manager=mock_plugin_manager,
            event_bus=mock_event_bus,
            orchestrator=mock_orchestrator,
            agent=mock_agent,
            session_manager=mock_session_manager,
            tool_executor=None,
            settings=None,
        )

        # Verify optional fields are None
        assert context.mcp_manager is None
        assert context.tool_executor is None
        assert context.settings is None


class TestCreateCoreContext:
    """Tests for create_core_context function."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        provider = MagicMock()
        provider.name = "test-provider"
        return provider

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock(spec=Settings)
        settings.providers = MagicMock(spec=ProviderSettings)
        settings.ui = MagicMock(spec=UISettings)
        settings.ui.mcp_logging = False
        settings.tools = MagicMock(spec=ToolSettings)
        settings.mcp_servers = None  # No MCP servers configured
        return settings

    @patch("henchman.cli.core_init.ToolManager")
    @patch("henchman.cli.core_init.PluginManager")
    @patch("henchman.cli.core_init.EventBus")
    @patch("henchman.cli.core_init.Orchestrator")
    @patch("henchman.cli.core_init.ReplSessionManager")
    def test_create_core_context_basic(
        self,
        mock_session_manager_cls,
        mock_orchestrator_cls,
        mock_event_bus_cls,
        mock_plugin_manager_cls,
        mock_tool_manager_cls,
        mock_provider,
        mock_settings,
    ):
        """Test basic creation of core context without MCP."""
        # Setup mocks
        mock_tool_manager = MagicMock()
        mock_tool_manager.registry = MagicMock()
        mock_tool_manager_cls.return_value = mock_tool_manager

        mock_plugin_manager = MagicMock()
        mock_plugin_manager_cls.return_value = mock_plugin_manager

        mock_event_bus = MagicMock()
        mock_event_bus_cls.return_value = mock_event_bus

        mock_orchestrator = MagicMock()
        mock_orchestrator.tech_lead = MagicMock()
        mock_orchestrator_cls.return_value = mock_orchestrator

        mock_session_manager = MagicMock()
        mock_session_manager_cls.return_value = mock_session_manager

        # Call function
        context = create_core_context(
            provider=mock_provider,
            system_prompt="Test system prompt",
            environment_context="Test environment",
            settings=mock_settings,
            auto_approve_tools=True,
        )

        # Verify context creation
        assert isinstance(context, CoreContext)
        assert context.provider == mock_provider
        assert context.tool_manager == mock_tool_manager
        assert context.tool_registry == mock_tool_manager.registry
        assert context.mcp_manager is None  # No MCP servers configured
        assert context.plugin_manager == mock_plugin_manager
        assert context.event_bus == mock_event_bus
        assert context.orchestrator == mock_orchestrator
        assert context.agent == mock_orchestrator.tech_lead
        assert context.session_manager == mock_session_manager
        assert context.tool_executor is None
        assert context.settings == mock_settings

        # Verify tool manager was configured
        mock_tool_manager.set_auto_approve.assert_called_once_with(auto_approve=True)
        mock_tool_manager.register_builtin_tools.assert_called_once()

        # Verify plugin manager loaded plugins
        mock_plugin_manager.load_plugins_from_directory.assert_called()

        # Verify orchestrator was created with correct arguments
        mock_orchestrator_cls.assert_called_once_with(
            default_provider=mock_provider,
            system_prompt="Test system prompt",
            environment_context="Test environment",
            event_bus=mock_event_bus,
            tool_registry=mock_tool_manager.registry,
            settings=mock_settings,
        )

    @patch("henchman.cli.core_init.ToolManager")
    @patch("henchman.cli.core_init.McpManager")
    @patch("henchman.cli.core_init.PluginManager")
    @patch("henchman.cli.core_init.EventBus")
    @patch("henchman.cli.core_init.Orchestrator")
    @patch("henchman.cli.core_init.ReplSessionManager")
    def test_create_core_context_with_mcp(
        self,
        mock_session_manager_cls,
        mock_orchestrator_cls,
        mock_event_bus_cls,
        mock_plugin_manager_cls,
        mock_mcp_manager_cls,
        mock_tool_manager_cls,
        mock_provider,
        mock_settings,
    ):
        """Test creation of core context with MCP servers configured."""
        # Setup mocks
        mock_tool_manager = MagicMock()
        mock_tool_manager.registry = MagicMock()
        mock_tool_manager_cls.return_value = mock_tool_manager

        mock_mcp_manager = MagicMock()
        mock_mcp_manager_cls.create_from_settings.return_value = mock_mcp_manager

        mock_plugin_manager = MagicMock()
        mock_plugin_manager_cls.return_value = mock_plugin_manager

        mock_event_bus = MagicMock()
        mock_event_bus_cls.return_value = mock_event_bus

        mock_orchestrator = MagicMock()
        mock_orchestrator.tech_lead = MagicMock()
        mock_orchestrator_cls.return_value = mock_orchestrator

        mock_session_manager = MagicMock()
        mock_session_manager_cls.return_value = mock_session_manager

        # Configure settings with MCP servers
        mock_settings.mcp_servers = {"test-server": {}}

        # Call function
        context = create_core_context(
            provider=mock_provider,
            settings=mock_settings,
            auto_approve_tools=False,
        )

        # Verify MCP manager was created
        assert context.mcp_manager == mock_mcp_manager
        mock_mcp_manager_cls.create_from_settings.assert_called_once_with(
            mock_settings, mcp_logging_enabled=False
        )

        # Verify orchestrator was created with MCP manager
        mock_orchestrator_cls.assert_called_once_with(
            default_provider=mock_provider,
            system_prompt="",
            environment_context=None,
            event_bus=mock_event_bus,
            tool_registry=mock_tool_manager.registry,
            settings=mock_settings,
        )

    @patch("henchman.cli.core_init.ToolManager")
    @patch("henchman.cli.core_init.PluginManager")
    @patch("henchman.cli.core_init.EventBus")
    @patch("henchman.cli.core_init.Orchestrator")
    @patch("henchman.cli.core_init.ReplSessionManager")
    def test_create_core_context_no_settings(
        self,
        mock_session_manager_cls,
        mock_orchestrator_cls,
        mock_event_bus_cls,
        mock_plugin_manager_cls,
        mock_tool_manager_cls,
        mock_provider,
    ):
        """Test creation of core context without settings."""
        # Setup mocks
        mock_tool_manager = MagicMock()
        mock_tool_manager.registry = MagicMock()
        mock_tool_manager_cls.return_value = mock_tool_manager

        mock_plugin_manager = MagicMock()
        mock_plugin_manager_cls.return_value = mock_plugin_manager

        mock_event_bus = MagicMock()
        mock_event_bus_cls.return_value = mock_event_bus

        mock_orchestrator = MagicMock()
        mock_orchestrator.tech_lead = MagicMock()
        mock_orchestrator_cls.return_value = mock_orchestrator

        mock_session_manager = MagicMock()
        mock_session_manager_cls.return_value = mock_session_manager

        # Call function without settings
        context = create_core_context(
            provider=mock_provider,
            auto_approve_tools=False,
        )

        # Verify context creation
        assert isinstance(context, CoreContext)
        assert context.provider == mock_provider
        assert context.mcp_manager is None  # No settings, so no MCP
        assert context.settings is None

        # Verify tool manager was not auto-approved
        mock_tool_manager.set_auto_approve.assert_called_once_with(auto_approve=False)


class TestInitializeMcp:
    """Tests for initialize_mcp function."""

    @patch("asyncio.create_task")
    def test_initialize_mcp_with_clients(self, mock_create_task):
        """Test initialize_mcp when MCP manager has no clients."""
        # Create mock context with MCP manager but no clients
        mock_context = MagicMock()
        mock_mcp_manager = MagicMock()
        mock_mcp_manager.clients = {}  # Empty clients dict
        mock_context.mcp_manager = mock_mcp_manager
        mock_context.tool_registry = MagicMock()

        # Call function
        initialize_mcp(mock_context)

        # Verify asyncio.create_task was called
        mock_create_task.assert_called_once()

        # Get the coroutine that was passed to create_task
        coro = mock_create_task.call_args[0][0]

        # Verify it's a coroutine
        assert asyncio.iscoroutine(coro)

        # We could run the coroutine to test it, but for now just verify
        # the structure is correct

    def test_initialize_mcp_no_mcp_manager(self):
        """Test initialize_mcp when there's no MCP manager."""
        # Create mock context without MCP manager
        mock_context = MagicMock()
        mock_context.mcp_manager = None

        # Call function - should do nothing
        initialize_mcp(mock_context)

        # No assertions needed - just shouldn't crash

    @patch("asyncio.create_task")
    def test_initialize_mcp_with_existing_clients(self, mock_create_task):
        """Test initialize_mcp when MCP manager already has clients."""
        # Create mock context with MCP manager that has clients
        mock_context = MagicMock()
        mock_mcp_manager = MagicMock()
        mock_mcp_manager.clients = {"server1": MagicMock()}  # Has clients
        mock_context.mcp_manager = mock_mcp_manager

        # Call function
        initialize_mcp(mock_context)

        # Should not create task since clients already exist
        mock_create_task.assert_not_called()
