from unittest.mock import MagicMock

import pytest

from henchman.cli.repl import Repl
from henchman.cli.session_manager import ReplSessionManager
from henchman.core.session import SessionManager
from henchman.tools.builtins import ReadFileTool, WriteFileTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_plan_mode_workflow(tmp_path):
    # Setup
    provider = MagicMock()
    # Mock provider.run to return a tool call followed by finished

    # We'll use actual tools but mock the provider response
    registry = ToolRegistry()
    write_tool = WriteFileTool()
    read_tool = ReadFileTool()
    registry.register(write_tool)
    registry.register(read_tool)

    repl = Repl(provider=provider)
    repl.tool_registry = registry
    manager = SessionManager(data_dir=tmp_path)
    repl.session_manager = ReplSessionManager(session_manager=manager, auto_save=False)
    session = manager.create_session("test-project")
    repl.set_session(session)

    # 1. Enable Plan Mode
    await repl.process_input("/plan")
    assert repl.session_manager.current.plan_mode is True
    assert registry._plan_mode is True

    # 2. Try to write a file (should be blocked)
    # We'll call registry.execute directly to verify the restriction
    result = await registry.execute(
        "write_file", {"path": str(tmp_path / "test.txt"), "content": "hello"}
    )
    assert not result.success
    assert "disabled in Plan Mode" in result.content
    assert not (tmp_path / "test.txt").exists()

    # 3. Read a file (should be allowed)
    test_file = tmp_path / "read.txt"
    test_file.write_text("content")
    result = await registry.execute("read_file", {"path": str(test_file)})
    assert result.success
    assert "content" in result.content

    # 4. Disable Plan Mode
    await repl.process_input("/plan")
    assert repl.session_manager.current.plan_mode is False
    assert registry._plan_mode is False

    # 5. Try to write a file (should be allowed now)
    # Mock confirmation to return True
    repl.config.auto_approve_tools = True
    result = await registry.execute(
        "write_file", {"path": str(tmp_path / "test.txt"), "content": "hello"}
    )
    assert result.success
    assert (tmp_path / "test.txt").exists()
    assert (tmp_path / "test.txt").read_text() == "hello"
