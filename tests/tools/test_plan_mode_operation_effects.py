"""Plan Mode per-invocation operation-effect classification (#18).

Plan Mode must classify each invocation by its effective operation effect,
not only the static catalog kind: read-only shell/python invocations stay
allowed, MCP remote tool calls (even from trusted servers) stay blocked,
and MCP management introspection actions stay allowed.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from henchman.mcp.client import McpToolDefinition
from henchman.mcp.tool import McpTool
from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.python_exec import PythonExecTool
from henchman.tools.builtins.shell import ShellTool
from henchman.tools.builtins.tier6_tools import McpAuthTool, MCPTool
from henchman.tools.registry import ToolRegistry


def _make_mcp_tool(*, trusted: bool) -> McpTool:
    client = MagicMock()
    definition = McpToolDefinition(
        name="do_work",
        description="Performs remote work",
        input_schema={"type": "object"},
    )
    return McpTool(mcp_tool=definition, client=client, server_name="srv", trusted=trusted)


class TestShellInvocationClassification:
    """Shell commands are classified per invocation, not statically."""

    def test_read_only_commands_are_read(self) -> None:
        tool = ShellTool()
        for command in (
            "ls -la",
            "cat src/main.py",
            "grep -rn TODO src",
            "rg error .",
            "wc -l build.txt",
            "echo hello",
            "pwd",
            "git status",
            "git log --oneline",
            "git diff --staged",
            "git show HEAD",
            "find . -name '*.py' -print",
            "FOO=bar ls",
        ):
            assert tool.execution_kind({"command": command}) is ToolKind.READ, command

    def test_effectful_commands_stay_execute(self) -> None:
        tool = ShellTool()
        for command in (
            "rm -rf /tmp/scratch",
            "echo hello > out.txt",
            "ls | grep x",
            "ls && rm x",
            "ls; rm x",
            "cat file $(rm -rf x)",
            "git push origin main",
            "git branch feature",
            "find . -name x -delete",
            "python -c 'print(1)'",
            "sudo ls",
            "mkdir /tmp/scratch",
            "",
        ):
            assert tool.execution_kind({"command": command}) is ToolKind.EXECUTE, command

    def test_missing_command_stays_execute(self) -> None:
        assert ShellTool().execution_kind({}) is ToolKind.EXECUTE

    async def test_read_only_shell_allowed_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(ShellTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("shell", {"command": "ls -la"})
        assert not isinstance(result, ToolResult)

    async def test_effectful_shell_blocked_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(ShellTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("shell", {"command": "rm -rf /tmp/scratch"})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"

    async def test_effectful_shell_allowed_when_plan_mode_off(self) -> None:
        registry = ToolRegistry()
        registry.register(ShellTool())
        registry.add_auto_approve_policy("shell")
        result = await registry.authorize("shell", {"command": "rm -rf /tmp/scratch"})
        assert isinstance(result, Tool)


class TestPythonExecInvocationClassification:
    """Python snippets are classified per invocation, not statically."""

    def test_read_only_sources_are_read(self) -> None:
        tool = PythonExecTool()
        for code in (
            "print(1 + 2)",
            "print(sorted([3, 1, 2]))",
            "print(len('abc'))",
            "print([i * 2 for i in range(3)])",
            "print({k: v for k, v in zip(['a', 'b'], [1, 2])})",
            "print(f'{1 + 1}')",
            "print('a' > 'b')",
            "print(-5, not True, ~1)",
            "print(1 if 0 else 2)",
            "print(1, sep=' ', end='')",
        ):
            assert tool.execution_kind({"code": code}) is ToolKind.READ, code

    def test_effectful_sources_stay_execute(self) -> None:
        tool = PythonExecTool()
        for code in (
            "import os",
            "from os import system",
            "open('f.txt')",
            "print(open('f.txt').read())",
            "x = 1",
            "x[0] = 1",
            "del x",
            "if True:\n    print(1)",
            "for i in range(3):\n    print(i)",
            "def f():\n    return 1",
            "class A:\n    pass",
            "lambda: 1",
            "print(eval('1'))",
            "print(__import__('os'))",
            "print(getattr(1, 'bit_length'))",
            "print((1).bit_length())",
            "print(x[0])",
            "print(x.attr)",
        ):
            assert tool.execution_kind({"code": code}) is ToolKind.EXECUTE, code

    async def test_read_only_python_allowed_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(PythonExecTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("python_exec", {"code": "print(1 + 2)"})
        assert not isinstance(result, ToolResult)

    async def test_effectful_python_blocked_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(PythonExecTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("python_exec", {"code": "import os"})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"


class TestMcpToolPlanModeBoundary:
    """Trusted MCP tools keep local auto-approval but cannot bypass Plan Mode."""

    def test_trusted_tool_catalog_kind_remains_read(self) -> None:
        assert _make_mcp_tool(trusted=True).kind is ToolKind.READ

    def test_trusted_tool_execution_kind_is_network(self) -> None:
        assert _make_mcp_tool(trusted=True).execution_kind({}) is ToolKind.NETWORK

    def test_untrusted_tool_execution_kind_is_network(self) -> None:
        assert _make_mcp_tool(trusted=False).execution_kind({}) is ToolKind.NETWORK

    def test_trusted_tool_needs_no_confirmation(self) -> None:
        assert _make_mcp_tool(trusted=True).needs_confirmation({}) is None

    def test_untrusted_tool_needs_confirmation(self) -> None:
        assert _make_mcp_tool(trusted=False).needs_confirmation({}) is not None

    async def test_trusted_tool_blocked_in_plan_mode(self) -> None:
        tool = _make_mcp_tool(trusted=True)
        registry = ToolRegistry()
        registry.register(tool)
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize(tool.name, {})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"

    async def test_untrusted_tool_blocked_in_plan_mode(self) -> None:
        tool = _make_mcp_tool(trusted=False)
        registry = ToolRegistry()
        registry.register(tool)
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize(tool.name, {})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"

    async def test_trusted_tool_allowed_when_plan_mode_off(self) -> None:
        tool = _make_mcp_tool(trusted=True)
        registry = ToolRegistry()
        registry.register(tool)
        result = await registry.authorize(tool.name, {})
        assert isinstance(result, Tool)


class TestMcpManagementToolClassification:
    """MCP management actions are classified per invocation, not statically."""

    def test_status_classified_read(self) -> None:
        assert MCPTool().execution_kind({"action": "status"}) is ToolKind.READ

    def test_discover_classified_read(self) -> None:
        assert MCPTool().execution_kind({"action": "discover"}) is ToolKind.READ

    def test_connect_stays_network(self) -> None:
        assert MCPTool().execution_kind({"action": "connect", "server": "srv"}) is ToolKind.NETWORK

    def test_disconnect_stays_network(self) -> None:
        assert MCPTool().execution_kind({"action": "disconnect", "server": "srv"}) is ToolKind.NETWORK

    def test_unsupported_action_stays_network(self) -> None:
        assert MCPTool().execution_kind({"action": "restart"}) is ToolKind.NETWORK

    async def test_status_allowed_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(MCPTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("mcp", {"action": "status"})
        assert not isinstance(result, ToolResult)

    async def test_connect_blocked_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(MCPTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("mcp", {"action": "connect", "server": "srv"})
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"

    def test_mcp_auth_status_classified_read(self) -> None:
        assert McpAuthTool().execution_kind({"action": "status"}) is ToolKind.READ

    def test_mcp_auth_set_stays_write(self) -> None:
        assert (
            McpAuthTool().execution_kind({"action": "set", "server": "srv", "token": "t"})
            is ToolKind.WRITE
        )

    async def test_mcp_auth_status_allowed_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(McpAuthTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize("mcp_auth", {"action": "status"})
        assert not isinstance(result, ToolResult)

    async def test_mcp_auth_set_blocked_in_plan_mode(self) -> None:
        registry = ToolRegistry()
        registry.register(McpAuthTool())
        registry.set_plan_mode(enabled=True)
        result = await registry.authorize(
            "mcp_auth", {"action": "set", "server": "srv", "token": "t"}
        )
        assert isinstance(result, ToolResult)
        assert result.error == "Tool disabled in Plan Mode"
