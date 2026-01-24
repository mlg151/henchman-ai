from unittest.mock import Mock, patch

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.skill import SkillCommand
from henchman.skills.models import Skill, SkillStep
from henchman.tools.base import ToolResult


@pytest.fixture
def ctx():
    console = Mock()
    session = Mock()
    session.messages = []
    tool_registry = Mock()
    return CommandContext(
        console=console,
        session=session,
        tool_registry=tool_registry,
        args=[]
    )

@pytest.mark.asyncio
async def test_skill_no_args(ctx):
    cmd = SkillCommand()
    await cmd.execute(ctx)
    ctx.console.print.assert_called()
    assert "Usage" in ctx.console.print.call_args[0][0]

@pytest.mark.asyncio
async def test_skill_unknown_subcommand(ctx):
    cmd = SkillCommand()
    ctx.args = ["invalid"]
    await cmd.execute(ctx)
    ctx.console.print.assert_called()
    assert "Unknown subcommand" in ctx.console.print.call_args[0][0]

@pytest.mark.asyncio
async def test_skill_list_empty(ctx):
    cmd = SkillCommand()
    ctx.args = ["list"]
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        mock_store.list_skills.return_value = []
        await cmd.execute(ctx)
        ctx.console.print.assert_called_with("[yellow]No skills learned yet.[/]")

@pytest.mark.asyncio
async def test_skill_list_with_items(ctx):
    cmd = SkillCommand()
    ctx.args = ["list"]
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        mock_store.list_skills.return_value = [
            Skill(name="s1", description="d1", steps=[])
        ]
        await cmd.execute(ctx)
        ctx.console.print.assert_any_call("  [cyan]s1[/] - d1")

@pytest.mark.asyncio
async def test_skill_show(ctx):
    cmd = SkillCommand()
    ctx.args = ["show", "s1"]
    skill = Skill(name="s1", description="d1", steps=[SkillStep(description="step1", tool="t1", arguments={})])
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        mock_store.load.return_value = skill
        await cmd.execute(ctx)
        ctx.console.print.assert_any_call("\n[bold cyan]Skill: s1[/]")

@pytest.mark.asyncio
async def test_skill_show_not_found(ctx):
    cmd = SkillCommand()
    ctx.args = ["show", "ghost"]
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        mock_store.load.side_effect = FileNotFoundError()
        await cmd.execute(ctx)
        ctx.console.print.assert_called_with("[red]Skill not found: ghost[/]")

@pytest.mark.asyncio
async def test_skill_show_no_args(ctx):
    cmd = SkillCommand()
    ctx.args = ["show"]
    await cmd.execute(ctx)
    ctx.console.print.assert_called_with("[red]Usage: /skill show <name>[/]")

@pytest.mark.asyncio
async def test_skill_run_no_registry(ctx):
    ctx.tool_registry = None
    cmd = SkillCommand()
    ctx.args = ["run", "s1"]
    await cmd.execute(ctx)
    ctx.console.print.assert_called_with("[red]Tool registry not available.[/]")

@pytest.mark.asyncio
async def test_skill_run_no_args(ctx):
    cmd = SkillCommand()
    ctx.args = ["run"]
    await cmd.execute(ctx)
    ctx.console.print.assert_called_with("[red]Usage: /skill run <name>[/]")

@pytest.mark.asyncio
async def test_skill_run_failure(ctx):
    cmd = SkillCommand()
    ctx.args = ["run", "s1"]
    skill = Skill(name="s1", description="d1", steps=[SkillStep(description="s", tool="t", arguments={})])
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore, \
         patch("henchman.cli.commands.skill.SkillExecutor") as MockExecutor:
        mock_store = MockStore.return_value
        mock_store.load.return_value = skill
        mock_executor = MockExecutor.return_value
        async def mock_run(_):
            yield ToolResult(content="fail", success=False, error="err")
        mock_executor.run.side_effect = mock_run
        await cmd.execute(ctx)
        ctx.console.print.assert_any_call("[red]✗[/] Error: err")

@pytest.mark.asyncio
async def test_skill_run_not_found(ctx):
    cmd = SkillCommand()
    ctx.args = ["run", "ghost"]
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        mock_store.load.side_effect = FileNotFoundError()
        await cmd.execute(ctx)
        ctx.console.print.assert_called_with("[red]Skill not found: ghost[/]")

@pytest.mark.asyncio
async def test_skill_delete(ctx):
    cmd = SkillCommand()
    ctx.args = ["delete", "s1"]
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        await cmd.execute(ctx)
        mock_store.delete.assert_called_with("s1")
        ctx.console.print.assert_called_with("[green]Skill deleted: s1[/]")

@pytest.mark.asyncio
async def test_skill_delete_no_args(ctx):
    cmd = SkillCommand()
    ctx.args = ["delete"]
    await cmd.execute(ctx)
    ctx.console.print.assert_called_with("[red]Usage: /skill delete <name>[/]")

@pytest.mark.asyncio
async def test_skill_learn_no_args(ctx):
    cmd = SkillCommand()
    ctx.args = ["learn"]
    await cmd.execute(ctx)
    ctx.console.print.assert_called_with("[red]Usage: /skill learn <name> <description>[/]")

@pytest.mark.asyncio
async def test_skill_learn_no_session(ctx):
    ctx.session = None
    cmd = SkillCommand()
    ctx.args = ["learn", "name", "desc"]
    await cmd.execute(ctx)
    ctx.console.print.assert_called_with("[red]No messages in current session to learn from.[/]")

@pytest.mark.asyncio
async def test_skill_learn_no_steps(ctx):
    from henchman.providers.base import Message
    cmd = SkillCommand()
    ctx.args = ["learn", "test-skill", "a test skill"]
    ctx.session.messages = [Message(role="user", content="hello")]
    with patch("henchman.cli.commands.skill.SkillStore"):
        await cmd.execute(ctx)
        ctx.console.print.assert_called_with("[yellow]No tool calls found in session to extract as a skill.[/]")

@pytest.mark.asyncio
async def test_skill_learn_success(ctx):
    from henchman.providers.base import Message, ToolCall
    cmd = SkillCommand()
    ctx.args = ["learn", "test-skill", "a test skill"]
    ctx.session.messages = [
        Message(role="assistant", tool_calls=[ToolCall(id="1", name="t1", arguments={})])
    ]
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        await cmd.execute(ctx)
        mock_store.save.assert_called_once()
        ctx.console.print.assert_called_with("[green]Learned new skill: test-skill[/]")
