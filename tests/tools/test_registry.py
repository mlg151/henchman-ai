"""Tests for ToolRegistry."""

import pytest

from henchman.tools.base import (
    ConfirmationRequest,
    Tool,
    ToolKind,
    ToolResult,
)
from henchman.tools.registry import BatchResult, ToolRegistry
from henchman.utils.retry import RetryConfig


class MockReadTool(Tool):
    """A mock read-only tool for testing."""

    @property
    def name(self) -> str:
        """Tool name."""
        return "read_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Read a file"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Read-only tool."""
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
        return "write_file"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Write to a file"

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
        """Write tool."""
        return ToolKind.WRITE

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool."""
        path = params.get("path", "")
        return ToolResult(content=f"Wrote to {path}")


class MockNetworkTool(Tool):
    """A mock network tool for testing retries."""

    def __init__(self) -> None:
        """Initialize with call counter."""
        self.call_count = 0

    @property
    def name(self) -> str:
        """Tool name."""
        return "fetch_url"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Fetch a URL"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
            },
            "required": ["url"],
        }

    @property
    def kind(self) -> ToolKind:
        """Network tool."""
        return ToolKind.NETWORK

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool."""
        self.call_count += 1
        url = params.get("url", "")
        return ToolResult(content=f"Fetched {url}")


class MockFailingNetworkTool(Tool):
    """A mock network tool that fails initially then succeeds."""

    def __init__(self, fail_count: int = 2) -> None:
        """Initialize with failure count."""
        self.call_count = 0
        self.fail_count = fail_count

    @property
    def name(self) -> str:
        """Tool name."""
        return "flaky_fetch"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Flaky fetch"

    @property
    def parameters(self) -> dict:
        """JSON Schema for parameters."""
        return {"type": "object", "properties": {}}

    @property
    def kind(self) -> ToolKind:
        """Network tool."""
        return ToolKind.NETWORK

    async def execute(self, **params: object) -> ToolResult:
        """Execute the tool, failing initially."""
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise ConnectionError("Network error")
        return ToolResult(content="Success after retry")


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_empty_registry(self) -> None:
        """New registry has no tools."""
        registry = ToolRegistry()
        assert registry.list_tools() == []
        assert registry.get_declarations() == []

    def test_register_tool(self) -> None:
        """Can register a tool."""
        registry = ToolRegistry()
        tool = MockReadTool()
        registry.register(tool)
        assert "read_file" in registry.list_tools()

    def test_register_multiple_tools(self) -> None:
        """Can register multiple tools."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        registry.register(MockWriteTool())
        tools = registry.list_tools()
        assert "read_file" in tools
        assert "write_file" in tools
        assert len(tools) == 2

    def test_get_tool(self) -> None:
        """Can retrieve a registered tool."""
        registry = ToolRegistry()
        tool = MockReadTool()
        registry.register(tool)
        retrieved = registry.get("read_file")
        assert retrieved is tool

    def test_get_nonexistent_tool(self) -> None:
        """Getting nonexistent tool returns None."""
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None

    def test_get_declarations(self) -> None:
        """Can get tool declarations for LLM."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        registry.register(MockWriteTool())
        declarations = registry.get_declarations()
        assert len(declarations) == 2
        names = {d.name for d in declarations}
        assert names == {"read_file", "write_file"}

    def test_duplicate_registration_raises(self) -> None:
        """Registering duplicate tool name raises error."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(MockReadTool())

    def test_unregister_tool(self) -> None:
        """Can unregister a tool."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        assert "read_file" in registry.list_tools()
        registry.unregister("read_file")
        assert "read_file" not in registry.list_tools()

    def test_unregister_nonexistent_silent(self) -> None:
        """Unregistering nonexistent tool is silent."""
        registry = ToolRegistry()
        registry.unregister("nonexistent")  # Should not raise


class TestToolRegistryExecution:
    """Tests for tool execution through registry."""

    async def test_execute_read_tool(self) -> None:
        """Execute a read tool through registry."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        result = await registry.execute("read_file", {"path": "/test.txt"})
        assert result.content == "Contents of /test.txt"
        assert result.success is True

    async def test_execute_nonexistent_tool(self) -> None:
        """Executing nonexistent tool returns error result."""
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", {})
        assert result.success is False
        assert "not found" in result.error.lower()

    async def test_execute_write_tool_without_confirmation(self) -> None:
        """Write tool executes when no confirmation handler set."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is True

    async def test_execute_with_confirmation_handler_approved(self) -> None:
        """Tool executes when confirmation handler approves."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        async def approve_handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            return True

        registry.set_confirmation_handler(approve_handler)
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is True
        assert result.content == "Wrote to /x"

    async def test_execute_with_confirmation_handler_denied(self) -> None:
        """Tool does not execute when confirmation handler denies."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        async def deny_handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            return False

        registry.set_confirmation_handler(deny_handler)
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is False
        assert "denied" in result.content.lower() or "denied" in result.error.lower()

    async def test_read_tool_skips_confirmation(self) -> None:
        """Read tools skip confirmation even with handler set."""
        registry = ToolRegistry()
        registry.register(MockReadTool())

        handler_called = False

        async def handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            nonlocal handler_called
            handler_called = True
            return False  # Would deny if called

        registry.set_confirmation_handler(handler)
        result = await registry.execute("read_file", {"path": "/test.txt"})
        assert result.success is True  # Still executed
        assert not handler_called  # Handler not invoked


class TestToolRegistryPolicyEngine:
    """Tests for PolicyEngine integration."""

    async def test_policy_auto_approve(self) -> None:
        """PolicyEngine can auto-approve tools."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        # Add policy that auto-approves write_file
        registry.add_auto_approve_policy("write_file")

        handler_called = False

        async def handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            nonlocal handler_called
            handler_called = True
            return False

        registry.set_confirmation_handler(handler)
        result = await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert result.success is True
        assert not handler_called  # Skipped due to policy

    async def test_policy_can_be_removed(self) -> None:
        """Auto-approve policies can be removed."""
        registry = ToolRegistry()
        registry.register(MockWriteTool())

        registry.add_auto_approve_policy("write_file")
        registry.remove_auto_approve_policy("write_file")

        handler_called = False

        async def handler(request: ConfirmationRequest) -> bool:  # noqa: ARG001
            nonlocal handler_called
            handler_called = True
            return True

        registry.set_confirmation_handler(handler)
        await registry.execute("write_file", {"path": "/x", "content": "y"})
        assert handler_called  # Handler invoked after policy removed

    def test_list_auto_approve_policies(self) -> None:
        """Can list auto-approve policies."""
        registry = ToolRegistry()
        registry.add_auto_approve_policy("write_file")
        registry.add_auto_approve_policy("shell")
        policies = registry.list_auto_approve_policies()
        assert "write_file" in policies
        assert "shell" in policies


class TestToolRegistryRetry:
    """Tests for retry logic in ToolRegistry."""

    async def test_network_tool_retries_on_failure(self) -> None:
        """Network tools are retried on transient failures."""
        tool = MockFailingNetworkTool(fail_count=2)
        registry = ToolRegistry(retry_config=RetryConfig(max_retries=3, base_delay=0.01))
        registry.register(tool)
        registry.add_auto_approve_policy("flaky_fetch")

        result = await registry.execute("flaky_fetch", {})
        assert result.success is True
        assert result.content == "Success after retry"
        assert tool.call_count == 3  # Failed twice, succeeded third time

    async def test_network_tool_exhausts_retries(self) -> None:
        """Network tools return error after exhausting retries."""
        tool = MockFailingNetworkTool(fail_count=10)  # Always fail
        registry = ToolRegistry(retry_config=RetryConfig(max_retries=2, base_delay=0.01))
        registry.register(tool)
        registry.add_auto_approve_policy("flaky_fetch")

        result = await registry.execute("flaky_fetch", {})
        assert result.success is False
        assert "Network error" in result.error
        assert tool.call_count == 3  # Initial + 2 retries

    async def test_non_network_tool_no_retry(self) -> None:
        """Non-network tools are not retried."""

        class FailingReadTool(Tool):
            """A read tool that always fails."""

            call_count = 0

            @property
            def name(self) -> str:
                return "failing_read"

            @property
            def description(self) -> str:
                return "Fails"

            @property
            def parameters(self) -> dict:
                return {"type": "object", "properties": {}}

            @property
            def kind(self) -> ToolKind:
                return ToolKind.READ

            async def execute(self, **params: object) -> ToolResult:
                FailingReadTool.call_count += 1
                raise ConnectionError("Should not retry")

        registry = ToolRegistry(retry_config=RetryConfig(max_retries=3, base_delay=0.01))
        registry.register(FailingReadTool())

        result = await registry.execute("failing_read", {})
        assert result.success is False
        assert FailingReadTool.call_count == 1  # No retries for READ tools

    async def test_set_retry_config(self) -> None:
        """Can update retry config after creation."""
        tool = MockFailingNetworkTool(fail_count=1)
        registry = ToolRegistry()  # Default config
        registry.set_retry_config(RetryConfig(max_retries=2, base_delay=0.01))
        registry.register(tool)
        registry.add_auto_approve_policy("flaky_fetch")

        result = await registry.execute("flaky_fetch", {})
        assert result.success is True
        assert tool.call_count == 2

    async def test_zero_retries_disables_retry(self) -> None:
        """Zero max_retries disables retry logic."""
        tool = MockFailingNetworkTool(fail_count=1)
        registry = ToolRegistry(retry_config=RetryConfig(max_retries=0))
        registry.register(tool)
        registry.add_auto_approve_policy("flaky_fetch")

        result = await registry.execute("flaky_fetch", {})
        assert result.success is False
        assert tool.call_count == 1


class TestToolRegistryBatch:
    """Tests for batch execution in ToolRegistry."""

    async def test_execute_batch_empty(self) -> None:
        """Empty batch returns empty result."""
        registry = ToolRegistry()
        result = await registry.execute_batch([])
        assert result.results == {}
        assert result.successful == 0
        assert result.failed == 0

    async def test_execute_batch_single(self) -> None:
        """Single tool in batch executes correctly."""
        registry = ToolRegistry()
        registry.register(MockReadTool())

        result = await registry.execute_batch(
            [
                ("read_file", {"path": "/test.txt"}),
            ]
        )

        assert result.successful == 1
        assert result.failed == 0
        assert len(result.results) == 1
        assert result.results["0:read_file"].content == "Contents of /test.txt"

    async def test_execute_batch_multiple(self) -> None:
        """Multiple tools execute in parallel."""
        registry = ToolRegistry()
        registry.register(MockReadTool())
        registry.register(MockWriteTool())

        result = await registry.execute_batch(
            [
                ("read_file", {"path": "/a.txt"}),
                ("read_file", {"path": "/b.txt"}),
                ("write_file", {"path": "/c.txt", "content": "hello"}),
            ]
        )

        assert result.successful == 3
        assert result.failed == 0
        assert len(result.results) == 3

    async def test_execute_batch_with_failures(self) -> None:
        """Batch continues executing even when some tools fail."""
        registry = ToolRegistry()
        registry.register(MockReadTool())

        result = await registry.execute_batch(
            [
                ("read_file", {"path": "/good.txt"}),
                ("nonexistent_tool", {}),
                ("read_file", {"path": "/also_good.txt"}),
            ]
        )

        assert result.successful == 2
        assert result.failed == 1
        assert result.results["0:read_file"].success is True
        assert result.results["1:nonexistent_tool"].success is False
        assert result.results["2:read_file"].success is True

    async def test_execute_batch_duplicate_tool_names(self) -> None:
        """Duplicate tool names get unique keys."""
        registry = ToolRegistry()
        registry.register(MockReadTool())

        result = await registry.execute_batch(
            [
                ("read_file", {"path": "/1.txt"}),
                ("read_file", {"path": "/2.txt"}),
                ("read_file", {"path": "/3.txt"}),
            ]
        )

        assert result.successful == 3
        assert "0:read_file" in result.results
        assert "1:read_file" in result.results
        assert "2:read_file" in result.results

    async def test_batch_result_dataclass(self) -> None:
        """BatchResult dataclass works correctly."""
        result = BatchResult(
            results={"tool_0": ToolResult(content="ok")},
            successful=1,
            failed=0,
        )
        assert result.successful == 1
        assert result.failed == 0
        assert result.results["tool_0"].content == "ok"

    async def test_execute_batch_exception_as_result(self) -> None:
        """BaseException from gather is converted to failed ToolResult."""
        from unittest.mock import patch

        from henchman.tools.builtins.file_read import ReadFileTool
        from henchman.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(ReadFileTool())

        # Patch execute to raise an exception
        with patch.object(registry, "execute", side_effect=RuntimeError("tool exploded")):
            result = await registry.execute_batch([("read_file", {"path": "test.txt"})])

        assert result.failed == 1
        assert "tool exploded" in list(result.results.values())[0].content


class TestRegistryCoverageGaps:
    """Additional tests for registry coverage gaps."""

    def test_len(self) -> None:
        """__len__ returns number of registered tools."""
        from henchman.tools.registry import ToolRegistry

        registry = ToolRegistry()
        assert len(registry) == 0

    async def test_execute_large_output_truncated(self) -> None:
        """Large tool output is truncated to prevent context overflow."""
        from henchman.tools.base import ToolKind, ToolResult
        from henchman.tools.registry import MAX_TOOL_OUTPUT, ToolRegistry

        # Build a tool that returns very large output
        class LargeTool(Tool):
            """Tool that returns very large output."""

            @property
            def name(self) -> str:
                """Tool name."""
                return "large_output_tool"

            @property
            def description(self) -> str:
                """Tool description."""
                return "Returns large output"

            @property
            def parameters(self) -> dict:
                """JSON Schema for parameters."""
                return {"type": "object", "properties": {}}

            @property
            def kind(self) -> ToolKind:
                """Read-only tool."""
                return ToolKind.READ

            async def execute(self, **params: object) -> ToolResult:
                """Return very large content."""
                return ToolResult(content="x" * (MAX_TOOL_OUTPUT + 1), success=True)

        registry = ToolRegistry()
        registry.register(LargeTool())
        result = await registry.execute("large_output_tool", {})
        assert result.success is True
        assert "truncated" in result.content

    async def test_execute_batch_base_exception(self) -> None:
        """BaseException from gather is converted to failed ToolResult (lines 294-299)."""
        from unittest.mock import patch

        from henchman.tools.registry import ToolRegistry

        registry = ToolRegistry()
        registry.register(MockReadTool())

        async def exploding_execute(name: str, params: dict) -> None:
            raise RuntimeError("tool exploded")

        with patch.object(registry, "execute", side_effect=RuntimeError("exploded again")):
            result = await registry.execute_batch([("read_file", {"path": "x.txt"})])

        assert result.failed == 1
        assert "exploded again" in list(result.results.values())[0].content
