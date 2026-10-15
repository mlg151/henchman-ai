"""Goals are real registered commands with persisted session state."""

from io import StringIO
from types import SimpleNamespace

from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.builtins import get_builtin_commands
from henchman.cli.commands.goal import GoalCommand
from henchman.core.goals import GoalService
from henchman.core.session_data import Session
from henchman.core.session_manager import SessionManager
from henchman.tools.builtins.goal_status import GoalStatusTool


async def test_registered_goal_command_persists_and_controls_goal(tmp_path) -> None:
    assert any(cmd.name == "goal" for cmd in get_builtin_commands())
    session = Session(id="test", project_hash="project", started="now", last_updated="now")
    manager = SessionManager(data_dir=tmp_path)
    ctx = CommandContext(console=Console(file=StringIO()), args=["Fix", "tests"],
                         session=session, session_manager=manager)
    command = GoalCommand()
    await command.execute(ctx)
    goal = GoalService().get(manager.load(session.id))
    assert goal.objective == "Fix tests"
    ctx.args = ["pause"]
    await command.execute(ctx)
    assert GoalService().get(session).status == "paused"
    ctx.args = ["resume"]
    await command.execute(ctx)
    assert GoalService().get(session).status == "active"
    ctx.args = ["complete"]
    await command.execute(ctx)
    assert GoalService().get(session).status == "complete"
    ctx.args = ["clear"]
    await command.execute(ctx)
    assert GoalService().get(manager.load(session.id)) is None


async def test_goal_status_tool_completes_only_matching_active_goal(tmp_path) -> None:
    session = Session(id="test", project_hash="project", started="now", last_updated="now")
    core_manager = SessionManager(data_dir=tmp_path)
    core_manager.set_current(session)
    tool = GoalStatusTool()
    tool.bind_runtime(session_manager=core_manager)
    service = GoalService()
    goal = service.start(session, "Fix tests")
    result = await tool.execute(action="complete", goal_id="obsolete", summary="Verified")
    assert not result.success
    assert service.get(session).status == "active"
    result = await tool.execute(action="complete", goal_id=goal.id, summary="Tests pass")
    assert result.success
    assert service.get(core_manager.load(session.id)).status == "complete"


async def test_goal_tool_requires_bound_session_and_cannot_pause() -> None:
    tool = GoalStatusTool()
    assert not (await tool.execute(action="status")).success
    session = Session(id="test", project_hash="project", started="now", last_updated="now")
    tool.bind_runtime(session_manager=SimpleNamespace(current=session))
    GoalService().start(session, "Work")
    assert not (await tool.execute(action="pause")).success
    assert GoalService().get(session).status == "active"
    assert (await tool.execute(action="status")).success


async def test_no_session_and_bad_subcommand_leave_clear_error() -> None:
    output = StringIO()
    command = GoalCommand()
    ctx = CommandContext(console=Console(file=output), args=["Fix", "tests"])
    await command.execute(ctx)
    assert "session" in output.getvalue().lower()


async def test_goal_completion_waits_for_background_processes(tmp_path) -> None:
    import sys

    from henchman.advanced.tasks import TaskService

    session = Session(id="test", project_hash="project", started="now", last_updated="now")
    goal = GoalService().start(session, "Wait for work")
    tool = GoalStatusTool()
    tool.bind_runtime(project_root=tmp_path, session_manager=SimpleNamespace(current=session))
    tasks = TaskService(project_root=tmp_path)
    running = await tasks.start_task(argv=[sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        result = await tool.execute(action="complete", goal_id=goal.id, summary="Done")
        assert not result.success
        assert running.task_id in result.content
        assert GoalService().get(session).status == "active"
    finally:
        await tasks.stop_task(running.task_id)
