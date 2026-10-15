import pytest

from henchman.tools.builtins.shell import ShellTool


@pytest.mark.asyncio
async def test_shell_pipes():
    tool = ShellTool()
    result = await tool.execute(background=False, command="echo 'hello world' | grep 'world'")
    assert result.success
    assert "world" in result.content
    assert "hello" in result.content


@pytest.mark.asyncio
async def test_shell_redirection(tmp_path):
    tool = ShellTool()
    test_file = tmp_path / "test.txt"
    result = await tool.execute(background=False, command=f"echo 'redirected' > {test_file}")
    assert result.success

    # Verify file content
    content = test_file.read_text().strip()
    assert content == "redirected"


@pytest.mark.asyncio
async def test_shell_timeout():
    tool = ShellTool()
    # Sleep for 2 seconds with 1 second timeout
    result = await tool.execute(background=False, command="sleep 2", timeout=1)
    assert not result.success
    assert "timeout" in result.error.lower()


@pytest.mark.asyncio
async def test_shell_multiline():
    tool = ShellTool()
    result = await tool.execute(background=False, command="echo 'line1'; echo 'line2'")
    assert result.success
    assert "line1" in result.content
    assert "line2" in result.content
