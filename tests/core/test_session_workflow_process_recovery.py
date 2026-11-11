"""Durable workflow ownership must not survive an actual process death."""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import henchman
from henchman.advanced.plans import PlanExecutionService
from henchman.config.schema import Settings
from henchman.core.session import SessionManager
from henchman.core.session_workflow import SessionWorkflow
from henchman.core.workflow_state import WorkflowError


def test_process_death_holds_queued_input_and_requires_goal_resume(tmp_path: Path) -> None:
    script = """
import asyncio
import json
import sys
import time
from pathlib import Path
from henchman.advanced.plans import PlanExecutionService
from henchman.config.schema import Settings
from henchman.core.session import SessionManager
from henchman.core.session_workflow import SessionWorkflow

root = Path(sys.argv[1])
manager = SessionManager(root / 'sessions')
session = manager.create_session('project')
session.plan_mode = True
manager.save(session)
settings = Settings()
settings.operations.persistence = 'durable'
settings.tools.network_access = 'disabled'
(root / 'value.txt').write_text('expected', encoding='utf-8')
plans = PlanExecutionService(root, settings=settings)
plan = plans.create_plan(steps=['Check'], checks=[
    {'kind': 'file_contains', 'path': 'value.txt', 'text': 'expected'}])
assert asyncio.run(plans.verify_plan(plan.plan_id))['current_checks_passed']
runtime = SessionWorkflow(settings, lambda: session, manager.save, root / 'ops.db',
                          check_status=plans.verification_status)
runtime.attach(session, restored=False)
runtime.start_goal('Finish the work')
goal = runtime.bind_plan(plan.plan_id)
started = runtime.submit('effect already dispatched')
queued = runtime.submit('later user input')
dispatch = runtime.next_input()
assert dispatch is not None and dispatch.permit.input_id == started.id
(root / 'effect').write_text('once', encoding='utf-8')
ready = root / 'ready.tmp'
ready.write_text(json.dumps({'session': session.id, 'goal': goal.id,
    'policy': goal.policy.model_dump(mode='json'), 'plan': plan.plan_id,
    'started': started.id, 'queued': queued.id}), encoding='utf-8')
ready.replace(root / 'ready')
while True:
    time.sleep(1)
"""
    env = os.environ.copy()
    package_root = str(Path(henchman.__file__).resolve().parent.parent)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, (package_root, env.get("PYTHONPATH", ""))))
    process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], env=env)
    try:
        deadline = time.monotonic() + 30
        ready = tmp_path / "ready"
        while not ready.exists():
            assert process.poll() is None, "Writer exited before the durable dispatch"
            assert time.monotonic() < deadline, "Writer never reached the dispatch boundary"
            time.sleep(0.02)
        identities = json.loads(ready.read_text(encoding="utf-8"))
        process.kill()
        process.wait(timeout=10)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)

    manager = SessionManager(tmp_path / "sessions")
    session = manager.load(identities["session"])
    settings = Settings()
    settings.operations.persistence = "durable"
    settings.tools.network_access = "disabled"
    plans = PlanExecutionService(tmp_path, settings=settings)
    runtime = SessionWorkflow(settings, lambda: session, manager.save, tmp_path / "ops.db",
                              check_status=plans.verification_status)
    runtime.attach(session, restored=True)
    report = runtime.report()
    first, second = report.state.inputs
    assert (first.id, first.state) == (identities["started"], "outcome_unknown")
    assert (second.id, second.state) == (identities["queued"], "queued")
    assert report.blocking_input_ids == (first.id,)
    assert runtime.goal().id == identities["goal"]
    assert runtime.goal().policy.model_dump(mode="json") == identities["policy"]
    assert runtime.goal().checks[0].plan_id == identities["plan"]
    assert not runtime.goal_continuation_allowed()
    assert runtime.next_input() is None
    assert (tmp_path / "effect").read_text(encoding="utf-8") == "once"
    assert plans.verification_status(identities["plan"])["status"] == "pass"
    (tmp_path / "value.txt").write_text("changed", encoding="utf-8")
    assert plans.verification_status(identities["plan"])["status"] == "stale"

    runtime.abandon(first.id, first.revision, "Inspected the prior effect; do not replay")
    assert runtime.next_input() is None
    runtime.send(second.id, second.revision)
    dispatch = runtime.next_input()
    assert dispatch is not None and dispatch.text == "later user input"
    runtime.finish(dispatch, outcome="success")
    resumed = runtime.resume_goal()
    assert resumed.id == identities["goal"] and runtime.goal_continuation_allowed()
    with pytest.raises(WorkflowError, match="goal_checks_unverified"):
        runtime.complete_goal(resumed.id, resumed.revision, "Claimed complete")
    (tmp_path / "value.txt").write_text("expected", encoding="utf-8")
    assert asyncio.run(plans.verify_plan(identities["plan"]))["current_checks_passed"]
    assert runtime.complete_goal(resumed.id, resumed.revision, "Checks pass").status == "complete"
    assert (tmp_path / "effect").read_text(encoding="utf-8") == "once"
