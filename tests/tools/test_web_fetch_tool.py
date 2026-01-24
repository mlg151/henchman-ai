"""Tests for web_fetch tool."""

from unittest.mock import AsyncMock, MagicMock, patch

from henchman.tools.base import ToolKind
from henchman.tools.builtins.web_fetch import WebFetchTool


class TestWebFetchTool:
    """Tests for WebFetchTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = WebFetchTool()
        assert tool.name == "web_fetch"

    def test_description(self) -> None:
        """Tool has description."""
        tool = WebFetchTool()
        assert "fetch" in tool.description.lower() or "url" in tool.description.lower()

    def test_kind_is_network(self) -> None:
        """Tool is a NETWORK kind (requires confirmation)."""
        tool = WebFetchTool()
        assert tool.kind == ToolKind.NETWORK

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = WebFetchTool()
        params = tool.parameters
        assert "url" in params["properties"]
        assert "url" in params["required"]

    async def test_fetch_success(self) -> None:
        """Successfully fetch a URL."""
        tool = WebFetchTool()

        # Create proper async context manager mocks
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="<html>Hello World</html>")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        mock_aiohttp.ClientTimeout = MagicMock()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.execute(url="https://example.com")

        assert result.success is True
        assert "Hello World" in result.content

    async def test_fetch_with_max_length(self) -> None:
        """Truncate response to max_length."""
        tool = WebFetchTool()

        long_content = "x" * 10000
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value=long_content)
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        mock_aiohttp.ClientTimeout = MagicMock()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.execute(url="https://example.com", max_length=100)

        assert result.success is True
        assert len(result.content) <= 150  # Allow buffer for truncation message

    async def test_fetch_error_status(self) -> None:
        """Handle HTTP error status."""
        tool = WebFetchTool()

        mock_response = MagicMock()
        mock_response.status = 404
        mock_response.text = AsyncMock(return_value="Not Found")
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        mock_aiohttp.ClientTimeout = MagicMock()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.execute(url="https://example.com/notfound")

        assert result.success is False
        assert "404" in result.content or "404" in str(result.error)

    async def test_fetch_connection_error(self) -> None:
        """Handle connection errors."""
        tool = WebFetchTool()

        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=Exception("Connection refused"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        mock_aiohttp.ClientTimeout = MagicMock()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.execute(url="https://unreachable.invalid")

        assert result.success is False
        assert result.error is not None

    async def test_fetch_timeout(self) -> None:
        """Handle request timeout."""
        tool = WebFetchTool()


        mock_session = MagicMock()
        mock_session.get = MagicMock(side_effect=TimeoutError())
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_aiohttp = MagicMock()
        mock_aiohttp.ClientSession = MagicMock(return_value=mock_session)
        mock_aiohttp.ClientTimeout = MagicMock()

        with patch.dict("sys.modules", {"aiohttp": mock_aiohttp}):
            result = await tool.execute(url="https://slow.example.com", timeout=1)

        assert result.success is False
        assert "timeout" in result.error.lower()
