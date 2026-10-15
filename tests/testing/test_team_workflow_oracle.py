"""Offline contracts for the production-team Python workflow evaluation."""

import json
from pathlib import Path

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.test_python_reuse import _NORMALIZATION, _TESTS

from henchman.config.schema import Settings
from henchman.providers.base import ToolCall

GOOD_CALLER = '''from normalization import normalize_label


def unique_labels(values: list[str]) -> list[str]:
    """Return canonical labels once each in input order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        label = normalize_label(value)
        if label and label not in seen:
            seen.add(label)
            result.append(label)
    return result
'''

GOOD_CLI = '''import argparse
import json

from label_index import unique_labels


def main(argv: list[str] | None = None) -> int:
    """Print the normalized labels supplied on the command line."""
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="*")
    print(json.dumps(unique_labels(parser.parse_args(argv).labels), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_outputs(workspace: Path, caller: str = GOOD_CALLER, cli: str = GOOD_CLI) -> None:
    (workspace / "normalization.py").write_text(_NORMALIZATION, encoding="utf-8")
    (workspace / "test_labels.py").write_text(_TESTS, encoding="utf-8")
    (workspace / "label_index.py").write_text(caller, encoding="utf-8")
    (workspace / "label_cli.py").write_text(cli, encoding="utf-8")


async def test_independent_checks_accept_reuse_and_real_cli(tmp_path: Path) -> None:
    from evals.test_team_python_workflow import verify_team_python_outputs

    write_outputs(tmp_path)
    checks = await verify_team_python_outputs(tmp_path)
    assert all(check["success"] for check in checks.values()), checks
    assert {"behavior", "cli", "ruff_lint", "black_format", "mypy"} <= checks.keys()


@pytest.mark.parametrize(
    "defect", ["copied_helper", "unchanged", "fake_cli", "early_exit", "type_error", "format"]
)
async def test_independent_checks_reject_false_passes(tmp_path: Path, defect: str) -> None:
    from evals.test_python_reuse import _CALLER
    from evals.test_team_python_workflow import verify_team_python_outputs

    caller, cli = GOOD_CALLER, GOOD_CLI
    if defect == "copied_helper":
        caller = caller.replace("from normalization import normalize_label", _NORMALIZATION.strip())
    elif defect == "unchanged":
        caller = _CALLER
    elif defect == "fake_cli":
        cli = 'print("[]")\n'
    elif defect == "early_exit":
        caller = "import os\nos._exit(0)\n" + caller
    elif defect == "type_error":
        caller = caller.replace("seen: set[str] = set()", 'seen: set[str] = "wrong"')
    elif defect == "format":
        caller = caller.replace("result: list[str] = []", "result:list[str]=[]")
    write_outputs(tmp_path, caller, cli)
    checks = await verify_team_python_outputs(tmp_path)
    assert not all(check["success"] for check in checks.values()), checks
    expected = {
        "copied_helper": "behavior",
        "unchanged": "behavior",
        "fake_cli": "cli",
        "early_exit": "behavior",
        "type_error": "mypy",
        "format": "black_format",
    }
    assert not checks[expected[defect]]["success"], checks


def tool(name: str, **arguments: object) -> list[ToolCall]:
    return [ToolCall(id=f"call-{name}", name=name, arguments=arguments)]


def team_script(*, defect: str | None = None) -> MockProvider:
    caller = GOOD_CALLER
    if defect == "copied_helper":
        caller = caller.replace("from normalization import normalize_label", _NORMALIZATION.strip())
    responses: list = [
        tool("delegate_task", agent="explorer", task="Inspect the existing helper and caller."),
        tool("read_file", path="normalization.py"),
        tool("read_file", path="label_index.py"),
        "Inspected the reusable helper and caller.",
        tool(
            "delegate_task",
            agent="engineer",
            task="Implement the caller and CLI, then run protected tests.",
        ),
        tool("write_file", path="label_index.py", content=caller),
        tool("write_file", path="label_cli.py", content=GOOD_CLI),
    ]
    if defect == "fixture_edit":
        responses.append(
            tool("write_file", path="normalization.py", content=_NORMALIZATION + "\n# Changed\n")
        )
    pytest_options: dict[str, object] = {}
    if defect == "filtered_tests":
        pytest_options["keyword"] = "normalization_and_duplicates"
    elif defect == "collect_only":
        pytest_options["collect_only"] = True
    responses.append(
        tool("shell", command="echo 4 passed")
        if defect == "fake_tests"
        else tool("pytest_run", path="test_labels.py", timeout=20, **pytest_options)
    )
    if defect == "test_before_final_edit":
        responses.append(tool("write_file", path="label_index.py", content=caller))
    responses.extend(
        [
            "Implementation and tests complete.",
            tool("delegate_task", agent="planner", task="Review both completed Python files."),
            tool("read_file", path="label_index.py"),
            tool("read_file", path="label_cli.py"),
            "Reviewed both files.",
            "The team completed the implementation and review.",
        ]
    )
    if defect == "same_batch_inspection":
        responses[:7] = [
            tool("delegate_task", agent="engineer", task="Inspect and implement the two files."),
            [
                *tool("read_file", path="normalization.py"),
                ToolCall("read-caller", "read_file", {"path": "label_index.py"}),
                *tool("write_file", path="label_index.py", content=caller),
                ToolCall("write-cli", "write_file", {"path": "label_cli.py", "content": GOOD_CLI}),
            ],
        ]
    return MockProvider(responses)


async def run_scenario(provider: MockProvider) -> dict:
    from evals.test_team_python_workflow import run_team_python_workflow

    settings = Settings(context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    rig = EvalTestRig(provider=provider, profile="team", settings=settings)
    try:
        rig.setup("team-workflow-oracle")
        return await run_team_python_workflow(rig, timeout=60)
    finally:
        rig.cleanup()


async def test_real_team_tools_satisfy_workflow_and_independent_checks(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONOPTIMIZE", "2")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    report = await run_scenario(team_script())
    assert report["success"], report
    assert report["task_verified"] is False
    assert report["workflow"]["inspection_before_edit"]
    assert report["workflow"]["engineer_edit"]
    assert report["workflow"]["post_edit_tests"]
    assert report["workflow"]["independent_review"]
    assert json.loads(json.dumps(report)) == report


@pytest.mark.parametrize(
    "defect",
    [
        "copied_helper",
        "fixture_edit",
        "fake_tests",
        "filtered_tests",
        "collect_only",
        "same_batch_inspection",
        "test_before_final_edit",
    ],
)
async def test_real_team_rejects_invalid_workflow_or_artifacts(defect: str) -> None:
    report = await run_scenario(team_script(defect=defect))
    assert not report["success"], report
    assert report["errors"]


async def test_correct_files_cannot_override_root_runtime_failure() -> None:
    class RootFailureProvider(MockProvider):
        async def chat_completion_stream(self, *args, **kwargs):
            if self._response_index == len(self._responses) - 1:
                raise RuntimeError("Root provider failed after the team finished")
            async for chunk in super().chat_completion_stream(*args, **kwargs):
                yield chunk

    provider = RootFailureProvider(team_script()._responses)
    report = await run_scenario(provider)
    assert all(check["success"] for check in report["checks"].values()), report
    assert not report["runtime"]["success"]
    assert not report["success"]


async def test_independent_behavior_ignores_stale_project_bytecode(tmp_path: Path) -> None:
    import os
    import py_compile

    from evals.test_team_python_workflow import verify_team_python_outputs

    write_outputs(tmp_path)
    source = tmp_path / "label_index.py"
    before = source.stat()
    py_compile.compile(str(source), doraise=True)
    broken = GOOD_CALLER.replace("return result", "return []".ljust(len("return result")))
    source.write_text(broken, encoding="utf-8")
    os.utime(source, ns=(before.st_atime_ns, before.st_mtime_ns))
    checks = await verify_team_python_outputs(tmp_path)
    assert not checks["behavior"]["success"]


async def test_correct_lone_agent_is_not_a_team_success() -> None:
    provider = MockProvider(
        [
            tool("read_file", path="normalization.py"),
            tool("write_file", path="label_index.py", content=GOOD_CALLER),
            tool("write_file", path="label_cli.py", content=GOOD_CLI),
            tool("pytest_run", path="test_labels.py", timeout=20),
            "Done",
        ]
    )
    # Explicit custom leader tools permit correct solo work; workflow still fails.
    from evals.test_team_python_workflow import run_team_python_workflow

    settings = Settings(
        context={"max_tokens": 32768},
        agents={
            "agents": {
                "tech_lead": {"tools": ["read_file", "write_file", "pytest_run"]},
            }
        },
    )
    rig = EvalTestRig(provider=provider, profile="team", settings=settings)
    try:
        rig.setup("solo-is-not-team")
        report = await run_team_python_workflow(rig, timeout=60)
    finally:
        rig.cleanup()
    assert all(check["success"] for check in report["checks"].values()), report
    assert not report["success"]
    assert not report["workflow"]["engineer_edit"]


async def test_verification_side_effect_cannot_change_protected_fixture(monkeypatch) -> None:
    from evals import test_team_python_workflow as scenario

    original = scenario.verify_team_python_outputs

    async def mutating_check(workspace: Path) -> dict:
        checks = await original(workspace)
        (workspace / "normalization.py").write_text("# replaced during import\n", encoding="utf-8")
        return checks

    monkeypatch.setattr(scenario, "verify_team_python_outputs", mutating_check)
    report = await run_scenario(team_script())
    assert not report["success"], report
    assert not report["checks"]["fixtures_unchanged"]["success"]


@pytest.mark.parametrize("executor", ["shell", "python_exec"])
async def test_late_execution_edit_requires_fresh_tests_and_review(executor: str) -> None:
    import os
    import shlex
    import subprocess
    import sys

    code = (
        "from pathlib import Path; p=Path('label_index.py'); "
        "p.write_text(p.read_text().replace('seen', 'seen_labels'))"
    )
    if executor == "shell":
        argv = [sys.executable, "-c", code]
        command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
        late_call = tool("shell", command=command, background=False)
    else:
        late_call = tool("python_exec", code=code, background=False)
    provider = team_script()
    if executor == "python_exec":
        provider._responses[-1:-1] = [
            tool("delegate_task", agent="engineer", task="Rename the local seen variable."),
            late_call,
            "Renamed the local variable.",
        ]
    else:
        provider._responses.insert(-1, late_call)
    report = await run_scenario(provider)
    assert any(
        item["tool_name"] == executor and item["success"]
        for item in report["workflow"]["observations"]
    ), report
    assert all(check["success"] for check in report["checks"].values()), report
    assert not report["success"], report
    assert not report["workflow"]["post_edit_tests"]
    assert not report["workflow"]["independent_review"]


async def test_late_read_only_shell_preserves_workflow_success() -> None:
    provider = team_script()
    provider._responses.insert(-1, tool("shell", command="echo verification-complete"))
    report = await run_scenario(provider)
    assert report["success"], report


async def test_change_after_last_event_requires_fresh_tests_and_review(monkeypatch) -> None:
    original = EvalTestRig.run

    async def mutate_after_run(self, *args, **kwargs):
        result = await original(self, *args, **kwargs)
        caller = self.test_dir / "label_index.py"
        caller.write_text(caller.read_text().replace("seen", "seen_labels"))
        return result

    monkeypatch.setattr(EvalTestRig, "run", mutate_after_run)
    report = await run_scenario(team_script())
    assert all(check["success"] for check in report["checks"].values()), report
    assert not report["success"], report
    assert not report["workflow"]["post_edit_tests"]
    assert not report["workflow"]["independent_review"]


@pytest.mark.parametrize("invalid", ["missing", "symlink", "oversize"])
def test_initial_unknown_snapshot_fails_closed(tmp_path: Path, invalid: str) -> None:
    from evals.test_team_python_workflow import _FIXTURES, _ArtifactTimeline, _fingerprint

    for name, content in _FIXTURES.items():
        (tmp_path / name).write_text(content)
    path = tmp_path / "label_index.py"
    path.unlink()
    if invalid == "symlink":
        path.symlink_to(tmp_path / "normalization.py")
    elif invalid == "oversize":
        path.write_bytes(b"x" * 1_048_577)
    initial = {name: _fingerprint(tmp_path / name) for name in _FIXTURES}
    timeline = _ArtifactTimeline(tmp_path, initial)
    # Restoring a readable source later must not erase the initial uncertainty.
    if path.is_symlink() or path.exists():
        path.unlink()
    path.write_text(GOOD_CALLER)
    observation = timeline.finish(0)
    assert observation["snapshot_errors"] == ["label_index.py"]
    assert not observation["complete"]


async def test_transient_unreadable_event_snapshot_fails_closed(monkeypatch) -> None:
    from evals import test_team_python_workflow as scenario

    original = scenario._fingerprint
    calls = 0

    def transient_failure(path: Path) -> str | None:
        nonlocal calls
        calls += 1
        if calls == len(scenario._FIXTURES) + 1:
            return None
        return original(path)

    monkeypatch.setattr(scenario, "_fingerprint", transient_failure)
    report = await run_scenario(team_script())
    assert not report["success"], report
    assert not report["checks"]["artifact_observation_complete"]["success"]


@pytest.mark.parametrize(
    "path,content,expected_success",
    [
        (".agent_tasks/notes.md", "Reviewed both implementations.\n", True),
        ("label_index.py", GOOD_CALLER, False),
    ],
)
async def test_late_file_write_timing_tracks_only_scenario_artifacts(
    path: str,
    content: str,
    expected_success: bool,
) -> None:
    provider = team_script()
    provider._responses[-1:-1] = [
        tool("delegate_task", agent="planner", task="Record the completed review notes."),
        tool("write_file", path=path, content=content),
        "Recorded review notes.",
    ]
    report = await run_scenario(provider)
    assert any(
        item["tool_name"] == "write_file" and item["path"] == path and item["success"]
        for item in report["workflow"]["observations"]
    ), report
    assert report["success"] is expected_success, report
    assert report["workflow"]["post_edit_tests"] is expected_success
    assert report["workflow"]["independent_review"] is expected_success
