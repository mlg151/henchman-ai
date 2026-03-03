"""Tests for MCP manager."""

from unittest.mock import MagicMock

from henchman.config.schema import Settings
from henchman.mcp.config import McpServerConfig
from henchman.mcp.manager import McpManager


class TestMcpManager:
    """Tests for McpManager class."""

    def test_init(self):
        """Test McpManager initialization."""
        configs = {
            "server1": McpServerConfig(
                command="python",
                args=["server.py"],
                env={"KEY": "value"},
                trusted=True,
            ),
            "server2": McpServerConfig(
                command="node",
                args=["server.js"],
                env={},
                trusted=False,
            ),
        }

        manager = McpManager(configs, verbose=True)

        assert manager.configs == configs
        assert manager.verbose is True
        assert manager.clients == {}
        assert manager._tools == []

    def test_get_server_names(self):
        """Test get_server_names method."""
        configs = {
            "server1": McpServerConfig(command="python", args=[], env={}, trusted=True),
            "server2": McpServerConfig(command="node", args=[], env={}, trusted=False),
        }

        manager = McpManager(configs)
        names = manager.get_server_names()

        assert set(names) == {"server1", "server2"}

    def test_is_trusted(self):
        """Test is_trusted method."""
        configs = {
            "server1": McpServerConfig(command="python", args=[], env={}, trusted=True),
            "server2": McpServerConfig(command="node", args=[], env={}, trusted=False),
        }

        manager = McpManager(configs)

        assert manager.is_trusted("server1") is True
        assert manager.is_trusted("server2") is False

    def test_is_trusted_unknown_server(self):
        """Test is_trusted with unknown server name."""
        configs = {
            "server1": McpServerConfig(command="python", args=[], env={}, trusted=True),
        }

        manager = McpManager(configs)

        # Should return False for unknown server
        assert manager.is_trusted("unknown") is False


class TestCreateFromSettings:
    """Tests for create_from_settings static method."""

    def test_create_from_settings_no_servers(self):
        """Test create_from_settings with no MCP servers configured."""
        # Mock settings with no MCP servers
        mock_settings = MagicMock(spec=Settings)
        mock_settings.mcp_servers = None

        result = McpManager.create_from_settings(mock_settings, mcp_logging_enabled=False)

        assert result is None

    def test_create_from_settings_empty_servers(self):
        """Test create_from_settings with empty MCP servers dict."""
        # Mock settings with empty MCP servers
        mock_settings = MagicMock(spec=Settings)
        mock_settings.mcp_servers = {}

        result = McpManager.create_from_settings(mock_settings, mcp_logging_enabled=False)

        assert result is None

    def test_create_from_settings_with_servers_no_logging(self):
        """Test create_from_settings with servers and logging disabled."""
        # Create mock settings with MCP servers
        mock_settings = MagicMock(spec=Settings)
        mock_settings.mcp_servers = {
            "python_server": MagicMock(
                command="python",
                args=["server.py"],
                env={"EXISTING": "value"},
                trusted=True,
            ),
            "node_server": MagicMock(
                command="node",
                args=["server.js"],
                env={},
                trusted=False,
            ),
            "serena_server": MagicMock(
                command="uvx",
                args=["serena", "start"],
                env={},
                trusted=True,
            ),
        }

        result = McpManager.create_from_settings(mock_settings, mcp_logging_enabled=False)

        # Should create McpManager
        assert isinstance(result, McpManager)
        assert result.verbose is False

        # Check server configurations
        assert "python_server" in result.configs
        assert "node_server" in result.configs
        assert "serena_server" in result.configs

        # Check Python server env (logging suppressed)
        python_config = result.configs["python_server"]
        assert python_config.command == "python"
        assert python_config.args == ["server.py"]
        assert python_config.trusted is True
        assert python_config.env["EXISTING"] == "value"
        assert python_config.env["PYTHONWARNINGS"] == "ignore"
        assert python_config.env["LOGLEVEL"] == "WARNING"
        assert python_config.env["PYTHON_LOG_LEVEL"] == "WARNING"
        assert python_config.env["NO_COLOR"] == "1"
        assert python_config.env["TERM"] == "dumb"

        # Check Node server env
        node_config = result.configs["node_server"]
        assert node_config.command == "node"
        assert node_config.args == ["server.js"]
        assert node_config.trusted is False
        assert node_config.env["NODE_ENV"] == "production"
        assert node_config.env["NO_COLOR"] == "1"
        assert node_config.env["TERM"] == "dumb"

        # Check Serena server env
        serena_config = result.configs["serena_server"]
        assert serena_config.command == "uvx"
        assert serena_config.args == ["serena", "start"]
        assert serena_config.trusted is True
        assert serena_config.env["SERENA_LOG_LEVEL"] == "WARNING"
        assert serena_config.env["PYTHONWARNINGS"] == "ignore"
        assert serena_config.env["LOGLEVEL"] == "WARNING"
        assert serena_config.env["PYTHON_LOG_LEVEL"] == "WARNING"
        assert serena_config.env["NO_COLOR"] == "1"
        assert serena_config.env["TERM"] == "dumb"

    def test_create_from_settings_with_servers_with_logging(self):
        """Test create_from_settings with servers and logging enabled."""
        # Create mock settings with MCP servers
        mock_settings = MagicMock(spec=Settings)
        mock_settings.mcp_servers = {
            "python_server": MagicMock(
                command="python",
                args=["server.py"],
                env={"EXISTING": "value"},
                trusted=True,
            ),
        }

        result = McpManager.create_from_settings(mock_settings, mcp_logging_enabled=True)

        # Should create McpManager with verbose=True
        assert isinstance(result, McpManager)
        assert result.verbose is True

        # Check server configuration (no logging suppression)
        python_config = result.configs["python_server"]
        assert python_config.command == "python"
        assert python_config.args == ["server.py"]
        assert python_config.trusted is True
        assert python_config.env["EXISTING"] == "value"
        # Should NOT have logging suppression env vars
        assert "PYTHONWARNINGS" not in python_config.env
        assert "LOGLEVEL" not in python_config.env
        assert "PYTHON_LOG_LEVEL" not in python_config.env
        # When logging is enabled, NO_COLOR and TERM should NOT be set
        assert "NO_COLOR" not in python_config.env
        assert "TERM" not in python_config.env

    def test_create_from_settings_uvx_python_server(self):
        """Test create_from_settings with uvx command (Python server)."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.mcp_servers = {
            "uvx_server": MagicMock(
                command="uvx",
                args=["mcp-server"],
                env={},
                trusted=True,
            ),
        }

        result = McpManager.create_from_settings(mock_settings, mcp_logging_enabled=False)

        uvx_config = result.configs["uvx_server"]
        # Should be detected as Python server
        assert "PYTHONWARNINGS" in uvx_config.env
        assert "LOGLEVEL" in uvx_config.env
        assert "PYTHON_LOG_LEVEL" in uvx_config.env

    def test_create_from_settings_npx_node_server(self):
        """Test create_from_settings with npx command (Node server)."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.mcp_servers = {
            "npx_server": MagicMock(
                command="npx",
                args=["mcp-server"],
                env={},
                trusted=True,
            ),
        }

        result = McpManager.create_from_settings(mock_settings, mcp_logging_enabled=False)

        npx_config = result.configs["npx_server"]
        # Should be detected as Node server
        assert npx_config.env["NODE_ENV"] == "production"

    def test_create_from_settings_py_file_server(self):
        """Test create_from_settings with .py file in args (Python server)."""
        mock_settings = MagicMock(spec=Settings)
        mock_settings.mcp_servers = {
            "pyfile_server": MagicMock(
                command="python3",
                args=["/path/to/server.py"],
                env={},
                trusted=True,
            ),
        }

        result = McpManager.create_from_settings(mock_settings, mcp_logging_enabled=False)

        pyfile_config = result.configs["pyfile_server"]
        # Should be detected as Python server
        assert "PYTHONWARNINGS" in pyfile_config.env
        assert "LOGLEVEL" in pyfile_config.env
        assert "PYTHON_LOG_LEVEL" in pyfile_config.env
