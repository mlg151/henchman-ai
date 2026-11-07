"""Explicit user queue disposition and goal policy controls."""

from io import StringIO

from rich.console import Console

from henchman.cli.commands import CommandContext
from henchman.cli.commands.goal import GoalCommand
from henchman.cli.commands.queue import QueueCommand
from henchman.core.goals import GoalService
from tests.core.test_session_workflow import controller


async def test_queue_edit_send_drop_and_stale_revision_are_explicit(tmp_path):
    runtime, session, _ = controller(tmp_path)
    first = runtime.submit("first")
    runtime.hold_pending()
    output = StringIO()
    ctx = CommandContext(Console(file=output, width=140), session=session)
    ctx.args = ["edit", first.id, str(first.revision), "changed", "request"]
    await QueueCommand().execute(ctx)
    edited = runtime.report().state.inputs[0]
    assert edited.text == "changed request" and runtime.next_input() is None
    ctx.args = ["send", first.id, str(first.revision)]
    await QueueCommand().execute(ctx)
    assert "revision_conflict" in output.getvalue() and runtime.next_input() is None
    ctx.args = ["send", first.id, str(edited.revision)]
    await QueueCommand().execute(ctx)
    dispatch = runtime.next_input()
    assert dispatch.text == "changed request"
    runtime.interrupt()
    current = runtime.report().state.inputs[0]
    ctx.args = ["send", current.id, str(current.revision)]
    await QueueCommand().execute(ctx)
    assert "input_not_queued" in output.getvalue()
    ctx.args = ["abandon", current.id, str(current.revision), "Inspected", "effects"]
    await QueueCommand().execute(ctx)
    assert not runtime.report().blocking_input_ids and runtime.next_input() is None


async def test_queue_status_redacts_before_clipping_and_renders_markup_literally(tmp_path):
    runtime, session, _ = controller(tmp_path)
    secret = "known-queue-canary"
    runtime.submit("[red]" + "a" * 490 + secret)
    session.evidence_redactor.register_secret(secret)
    output = StringIO()
    ctx = CommandContext(Console(file=output, width=1600), session=session)
    await QueueCommand().execute(ctx)
    assert secret not in output.getvalue()
    assert "[red]" in output.getvalue()
    assert "preview truncated" in output.getvalue()


async def test_goal_resume_policy_acknowledgement_and_user_completion(tmp_path):
    runtime, session, _ = controller(tmp_path)
    goal = GoalService().start(session, "objective")
    runtime.hold_pending()
    session.plan_mode = True
    output = StringIO()
    ctx = CommandContext(Console(file=output), session=session, args=["resume"])
    await GoalCommand().execute(ctx)
    assert "goal_policy_changed" in output.getvalue()
    assert not runtime.goal_continuation_allowed()
    ctx.args = ["resume", "--accept-policy-change"]
    await GoalCommand().execute(ctx)
    assert runtime.goal_continuation_allowed() and runtime.goal().id == goal.id
    ctx.args = ["pause"]
    await GoalCommand().execute(ctx)
    ctx.args = ["complete"]
    await GoalCommand().execute(ctx)
    assert runtime.goal().status == "complete"
    assert runtime.goal().completion_summary == "Completed by user"
    assert runtime.goal().completion_source == "user"


async def test_queue_edit_preserves_raw_multiline_input(tmp_path):
    runtime, session, _ = controller(tmp_path)
    item = runtime.submit("initial")
    text = 'Use "these  spaces"\nand this newline'
    ctx = CommandContext(Console(file=StringIO()), session=session,
                         args=["edit", item.id, str(item.revision), *text.split()],
                         raw_input=f"/queue edit {item.id} {item.revision} {text}")
    await QueueCommand().execute(ctx)
    assert runtime.report().state.inputs[0].text == text
