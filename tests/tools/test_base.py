"""Tests for tool base classes and types."""

from henchman.tools.base import (
    ConfirmationRequest,
    Tool,
    ToolKind,
    ToolResult,
)


class TestToolKind:
    """Tests for ToolKind enum."""

    def test_read_value(self) -> None:
        """READ kind has correct value."""
        assert ToolKind.READ.value == "read"

    def test_write_value(self) -> None:
        """WRITE kind has correct value."""
        assert ToolKind.WRITE.value == "write"

    def test_execute_value(self) -> None:
        """EXECUTE kind has correct value."""
        assert ToolKind.EXECUTE.value == "execute"

    def test_network_value(self) -> None:
        """NETWORK kind has correct value."""
        assert ToolKind.NETWORK.value == "network"

    def test_all_kinds_exist(self) -> None:
        """All expected tool kinds exist."""
        kinds = {k.value for k in ToolKind}
        assert kinds == {"read", "write", "execute", "network"}


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_minimal_result(self) -> None:
        """ToolResult with only content."""
        result = ToolResult(content="file contents")
        assert result.content == "file contents"
        assert result.success is True
        assert result.display is None
        assert result.error is None

    def test_full_result(self) -> None:
        """ToolResult with all fields."""
        result = ToolResult(
            content="data for model",
            success=True,
            display="pretty output for user",
            error=None,
        )
        assert result.content == "data for model"
        assert result.display == "pretty output for user"

    def test_error_result(self) -> None:
        """ToolResult representing an error."""
        result = ToolResult(
            content="Error: file not found",
            success=False,
            error="FileNotFoundError: /path/to/file",
        )
        assert result.success is False
        assert result.error == "FileNotFoundError: /path/to/file"


class TestConfirmationRequest:
    """Tests for ConfirmationRequest dataclass."""

    def test_basic_request(self) -> None:
        """ConfirmationRequest with required fields."""
        request = ConfirmationRequest(
            tool_name="write_file",
            description="Write to /etc/passwd",
        )
        assert request.tool_name == "write_file"
        assert request.description == "Write to /etc/passwd"
        assert request.params is None
        assert request.risk_level == "medium"

    def test_high_risk_request(self) -> None:
        """ConfirmationRequest with high risk level."""
        request = ConfirmationRequest(
            tool_name="shell",
            description="Execute: rm -rf /",
            params={"command": "rm -rf /"},
            risk_level="high",
        )
        assert request.risk_level == "high"
        assert request.params == {"command": "rm -rf /"}


class MockReadTool(Tool):
    """A mock read-only tool for testing."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "mock_read"

    @property
    def description(self) -> str:
        """Tool description."""
        return "A mock read tool"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path"},
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """This is a read-only tool."""
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool."""
        path = params.get("path", "")
        return ToolResult(content=f"Contents of {path}")


class MockWriteTool(Tool):
    """A mock write tool for testing."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "mock_write"

    @property
    def description(self) -> str:
        """Tool description."""
        return "A mock write tool"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        }

    @property
    def kind(self) -> ToolKind:
        """This is a write tool."""
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool."""
        path = params.get("path", "")
        return ToolResult(content=f"Wrote to {path}")


class MockDefaultKindTool(Tool):
    """A mock tool that doesn't override kind (uses default READ)."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "mock_default"

    @property
    def description(self) -> str:
        """Tool description."""
        return "A mock tool with default kind"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {"type": "object", "properties": {}}

    async def execute(self, **params: object) -> ToolResult:  # noqa: ARG002
        """Execute the tool."""
        return ToolResult(content="executed")


class TestToolABC:
    """Tests for Tool abstract base class."""

    def test_read_tool_properties(self) -> None:
        """Read tool has correct properties."""
        tool = MockReadTool()
        assert tool.name == "mock_read"
        assert tool.description == "A mock read tool"
        assert tool.kind == ToolKind.READ
        assert "path" in tool.parameters["properties"]

    def test_write_tool_properties(self) -> None:
        """Write tool has correct properties."""
        tool = MockWriteTool()
        assert tool.name == "mock_write"
        assert tool.kind == ToolKind.WRITE

    def test_default_kind_is_read(self) -> None:
        """Tool without overridden kind defaults to READ."""
        tool = MockDefaultKindTool()
        assert tool.kind == ToolKind.READ

    def test_read_tool_no_confirmation_needed(self) -> None:
        """Read tools don't need confirmation by default."""
        tool = MockReadTool()
        request = tool.needs_confirmation({"path": "/some/file"})
        assert request is None

    def test_write_tool_needs_confirmation(self) -> None:
        """Write tools need confirmation by default."""
        tool = MockWriteTool()
        request = tool.needs_confirmation({"path": "/etc/passwd", "content": "x"})
        assert request is not None
        assert isinstance(request, ConfirmationRequest)
        assert request.tool_name == "mock_write"
        assert request.risk_level == "medium"

    def test_execute_tool_high_risk(self) -> None:
        """Execute tools have high risk level."""

        class MockExecuteTool(Tool):
            """Mock execute tool."""

            @property
            def name(self) -> str:
                """Tool name."""
                return "shell"

            @property
            def description(self) -> str:
                """Tool description."""
                return "Execute shell command"

            @property
            def parameters(self) -> dict:
                """JSON Schema."""
                return {"type": "object", "properties": {"cmd": {"type": "string"}}}

            @property
            def kind(self) -> ToolKind:
                """Execute kind."""
                return ToolKind.EXECUTE

            async def execute(self, **params: object) -> ToolResult:  # noqa: ARG002
                """Execute."""
                return ToolResult(content="done")

        tool = MockExecuteTool()
        request = tool.needs_confirmation({"cmd": "rm -rf /"})
        assert request is not None
        assert request.risk_level == "high"

    def test_network_tool_needs_confirmation(self) -> None:
        """Network tools need confirmation with medium risk."""

        class MockNetworkTool(Tool):
            """Mock network tool."""

            @property
            def name(self) -> str:
                """Tool name."""
                return "web_fetch"

            @property
            def description(self) -> str:
                """Tool description."""
                return "Fetch URL"

            @property
            def parameters(self) -> dict:
                """JSON Schema."""
                return {"type": "object", "properties": {"url": {"type": "string"}}}

            @property
            def kind(self) -> ToolKind:
                """Network kind."""
                return ToolKind.NETWORK

            async def execute(self, **params: object) -> ToolResult:  # noqa: ARG002
                """Execute."""
                return ToolResult(content="fetched")

        tool = MockNetworkTool()
        request = tool.needs_confirmation({"url": "http://example.com"})
        assert request is not None
        assert request.risk_level == "medium"

    def test_to_declaration(self) -> None:
        """Tool can be converted to ToolDeclaration."""
        tool = MockReadTool()
        declaration = tool.to_declaration()
        assert declaration.name == "mock_read"
        assert declaration.description == "A mock read tool"
        assert declaration.parameters == tool.parameters


class TestToolExecution:
    """Tests for tool execution."""

    async def test_execute_read_tool(self) -> None:
        """Execute a read tool."""
        tool = MockReadTool()
        result = await tool.execute(path="/test/file.txt")
        assert result.content == "Contents of /test/file.txt"
        assert result.success is True

    async def test_execute_write_tool(self) -> None:
        """Execute a write tool."""
        tool = MockWriteTool()
        result = await tool.execute(path="/test/output.txt", content="hello")
        assert result.content == "Wrote to /test/output.txt"
        assert result.success is True
