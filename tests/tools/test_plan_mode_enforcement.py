"""Test plan mode enforcement for write/execute tools."""


from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.registry import ToolRegistry


class MockWriteTool(Tool):
    """A mock write tool for testing."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write to a file"

    @property
    def parameters(self) -> dict:
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
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="Executed write_file")


class MockExecuteTool(Tool):
    """A mock execute tool for testing."""

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute shell command"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
            },
            "required": ["command"],
        }

    @property
    def kind(self) -> ToolKind:
        return ToolKind.EXECUTE

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="Executed shell")


class MockReadTool(Tool):
    """A mock read tool for testing."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read a file"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="Executed read_file")


class TestPlanModeEnforcement:
    """Tests for plan mode enforcement in ToolRegistry."""

    async def test_write_tool_blocked_in_plan_mode(self) -> None:
        """Write tools should be blocked in plan mode."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        # Enable plan mode
        registry.set_plan_mode(True)

        result = await registry.execute("write_file", {"path": "/test", "content": "data"})
        assert result.success is False
        assert "disabled in Plan Mode" in result.content
        assert result.error == "Tool disabled in Plan Mode"

    async def test_execute_tool_blocked_in_plan_mode(self) -> None:
        """Execute tools should be blocked in plan mode."""
        registry = ToolRegistry()
        registry.register(MockExecuteTool())

        # Enable plan mode
        registry.set_plan_mode(True)

        result = await registry.execute("shell", {"command": "ls"})
        assert result.success is False
        assert "disabled in Plan Mode" in result.content
        assert result.error == "Tool disabled in Plan Mode"

    async def test_read_tool_allowed_in_plan_mode(self) -> None:
        """Read tools should be allowed in plan mode."""
        registry = ToolRegistry()
        registry.register(MockReadTool())

        # Enable plan mode
        registry.set_plan_mode(True)

        result = await registry.execute("read_file", {"path": "/test"})
        assert result.success is True
        assert "Executed read_file" in result.content

    async def test_write_tool_allowed_when_plan_mode_disabled(self) -> None:
        """Write tools should work when plan mode is disabled."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        # Plan mode disabled (default)
        registry.set_plan_mode(False)

        result = await registry.execute("write_file", {"path": "/test", "content": "data"})
        assert result.success is True
        assert "Executed write_file" in result.content

    async def test_network_tool_blocked_in_plan_mode(self) -> None:
        """Network tools should be blocked in plan mode."""
        class MockNetworkTool(Tool):
            @property
            def name(self) -> str:
                return "web_fetch"

            @property
            def description(self) -> str:
                return "Fetch URL"

            @property
            def parameters(self) -> dict:
                return {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                    },
                    "required": ["url"],
                }

            @property
            def kind(self) -> ToolKind:
                return ToolKind.NETWORK

            async def execute(self, **params: object) -> ToolResult:
                return ToolResult(content="Executed web_fetch")

        registry = ToolRegistry()
        registry.register(MockNetworkTool())

        # Enable plan mode
        registry.set_plan_mode(True)

        result = await registry.execute("web_fetch", {"url": "http://example.com"})
        assert result.success is False
        assert "disabled in Plan Mode" in result.content
        assert result.error == "Tool disabled in Plan Mode"
