"""Production team completion is separate from independently verified packages."""

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.package_oracle import EDITABLE_FILES

from henchman.config.schema import Settings
from henchman.providers.base import ToolCall

LIBRARY = """import label_rules


def unique_labels(values: list[str]) -> list[str]:
    labels = [label_rules.normalize_label(value) for value in values]
    return list(dict.fromkeys(label for label in labels if label))
"""
CLI = """import argparse
import json
from importlib.resources import files

from release_labels import unique_labels


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("labels", nargs="*")
    args = parser.parse_args()
    defaults = json.loads(files("release_labels").joinpath("data/defaults.json").read_text())
    print(json.dumps({defaults["key"]: unique_labels(args.labels)}))
    return 0
"""
BUILD = """import shutil
import subprocess

subprocess.run([shutil.which("uv"), "--no-config", "--offline",
                "--no-python-downloads", "build", "--wheel", "--out-dir", "dist"],
               check=True, timeout=60)
"""


def tool(name: str, **arguments: object) -> list[ToolCall]:
    return [ToolCall(f"package-{name}", name, arguments)]


def script(defect: str | None = None) -> MockProvider:
    responses: list[str | list[ToolCall]] = [
        tool("delegate_task", agent="explorer", task="Inspect the package.")
    ]
    responses.extend(
        tool("read_file", path=name)
        for name in (
            EDITABLE_FILES[0],
            "reference/label_rules.py",
            "pyproject.toml",
            "tests/test_installed.py",
            ".github/workflows/ci.yml",
        )
        if not (defect == "no_dependency_inspection" and name == "reference/label_rules.py")
    )
    responses.extend(
        [
            "STATUS: success\nSUMMARY: Inspected implementation and packaging contracts.",
            tool(
                "delegate_task",
                agent="engineer",
                task="Implement the library and CLI; build wheel.",
            ),
            tool("write_file", path=EDITABLE_FILES[0], content=LIBRARY),
            tool("write_file", path=EDITABLE_FILES[1], content=CLI),
            tool("python_exec", code=BUILD, timeout=90, background=False),
            "STATUS: success\nSUMMARY: Implemented and built the final offline wheel.",
        ]
    )
    if defect == "foreign_final_edit":
        code = (
            "from pathlib import Path; p = Path('src/release_labels/__init__.py'); "
            "p.write_text(p.read_text() + chr(10) + 'FOREIGN_CHANGE = True' + chr(10))"
        )
        argv = [sys.executable, "-c", code]
        command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
        uv = shutil.which("uv")
        assert uv, "The offline package task requires uv"
        build_argv = [
            uv,
            "--no-config",
            "--offline",
            "--no-python-downloads",
            "build",
            "--wheel",
            "--out-dir",
            "dist",
        ]
        build_command = (
            subprocess.list2cmdline(build_argv) if os.name == "nt" else shlex.join(build_argv)
        )
        responses.extend(
            [
                tool("shell", command=command, background=False),
                tool("shell", command=build_command, background=False),
                tool(
                    "delegate_task", agent="engineer", task="Read the latest source; do not edit."
                ),
                tool("read_file", path=EDITABLE_FILES[0]),
                "STATUS: success\nSUMMARY: Read the latest source.",
            ]
        )
    if defect != "no_review":
        responses.extend(
            [
                tool(
                    "delegate_task", agent="planner", task="Review both final implementation files."
                ),
                tool("read_file", path=EDITABLE_FILES[0]),
                tool("read_file", path=EDITABLE_FILES[1]),
                (
                    "STATUS: failed\nBLOCKERS: Review found unresolved requirements."
                    if defect == "failed_review"
                    else "STATUS: success\nSUMMARY: Reviewed final implementation and package contract."
                ),
            ]
        )
    if defect in ("late_edit", "build_before_format"):
        mutate = (
            "from pathlib import Path\np = Path('src/release_labels/__init__.py')\n"
            "p.write_text(p.read_text() + '\\nFINAL_CHANGE = True\\n')\n"
        )
        responses.append(
            tool("delegate_task", agent="engineer", task="Update the final source and rebuild.")
        )
        if defect == "build_before_format":
            # Foreground shell formats changed workspace sources after the wheel
            # build. python_exec intentionally formats only its input snippet.
            # Shell validation requires a single line without newline escapes.
            code = (
                "from pathlib import Path; import shutil, subprocess; "
                "p = Path('src/release_labels/__init__.py'); "
                "p.write_text(p.read_text() + chr(10) + 'FINAL_CHANGE = True' + chr(10)); "
                "subprocess.run([shutil.which('uv'), '--no-config', '--offline', "
                "'--no-python-downloads', 'build', '--wheel', '--out-dir', 'dist'], "
                "check=True, timeout=60)"
            )
            argv = [sys.executable, "-c", code]
            command = subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)
            responses.append(tool("shell", command=command, timeout=90, background=False))
        else:
            responses.append(tool("python_exec", code=mutate, timeout=90, background=False))
            responses.append(tool("python_exec", code=BUILD, timeout=90, background=False))
        responses.append("STATUS: success\nSUMMARY: Updated final source and rebuilt the wheel.")
    responses.append("The required implementation and wheel are ready.")
    return MockProvider(responses)


async def run(provider: MockProvider) -> dict[str, Any]:
    from evals.test_team_python_package import run_team_python_package

    settings = Settings(context={"max_tokens": 32768})
    settings.agents.max_delegation_retries = 0
    rig = EvalTestRig(provider=provider, profile="team", settings=settings)
    try:
        rig.setup("package-scenario-contract")
        return await run_team_python_package(rig, timeout=90)
    finally:
        rig.cleanup()


async def test_production_team_and_real_independent_package_pipeline_pass() -> None:
    report = await run(script())
    assert report["success"], (report["errors"], report["workflow"], report["package"])
    assert report["task_verified"] is False
    assert report["package"]["artifacts"]["executed_tests"] == 5
    assert report["workflow"]["independent_review_completed"] is True
    assert report["agent_install_test_execution"] == "not_attested"


@pytest.mark.parametrize("defect", ["no_review", "late_edit", "failed_review"])
async def test_correct_package_without_review_of_final_source_fails(defect: str) -> None:
    report = await run(script(defect))
    assert report["package"]["success"], report
    assert not report["success"]
    assert not report["workflow"]["independent_review_completed"]


async def test_engineer_participation_cannot_claim_another_actors_final_change() -> None:
    report = await run(script("foreign_final_edit"))
    assert any(
        item["tool_name"] == "shell" and item["source_agent"] == "tech_lead" and item["success"]
        for item in report["tool_observations"]
    ), report
    assert report["package"]["success"], report
    assert report["workflow"]["independent_review_completed"], report
    assert not report["success"]
    assert not report["workflow"]["engineer_edit"]


async def test_omitted_dependency_inspection_cannot_pass_with_correct_artifacts() -> None:
    report = await run(script("no_dependency_inspection"))
    assert report["package"]["success"], report
    assert not report["success"]
    assert not report["workflow"]["inspection_before_edit"]


async def test_wheel_built_before_automatic_formatting_requires_rebuild() -> None:
    report = await run(script("build_before_format"))
    assert any(
        item["tool_name"] == "shell" and item["source_agent"] == "engineer" and item["success"]
        for item in report["tool_observations"]
    ), report
    assert not report["success"]
    check = report["package"]["checks"]["wheel_matches_source"]
    assert not check["success"]
    assert "rebuilt final source" in check["error"]


async def test_independent_pipeline_cannot_overrule_authoritative_root_failure(monkeypatch) -> None:
    original = EvalTestRig.run

    async def failed_root(self, *args, **kwargs):
        result = await original(self, *args, **kwargs)
        result.success = False
        result.error = "Authoritative root failure"
        return result

    monkeypatch.setattr(EvalTestRig, "run", failed_root)
    report = await run(script())
    assert report["package"]["success"], report
    assert not report["success"]
    assert "Authoritative root failure" in report["errors"]


async def test_non_team_profile_fails_before_creating_package(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from evals.test_team_python_package import run_team_python_package

    rig = SimpleNamespace(profile_metadata={"profile": "basic"}, test_dir=tmp_path)
    report = await run_team_python_package(cast(EvalTestRig, rig))
    assert not report["success"]
    assert not list(tmp_path.iterdir())
