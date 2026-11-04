"""Offline contracts for the actual Python helper-reuse scenario."""

import os
import shlex
import subprocess
import sys

import pytest
from evals.helpers import EvalTestRig, MockProvider
from evals.test_python_reuse import run_python_reuse_scenario

from henchman.providers import ToolCall

CORRECT_IMPLEMENTATION = """
from normalization import normalize_label

def unique_labels(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        normalized = normalize_label(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
"""


def get_pytest_command() -> str:
    argv = [sys.executable, "-m", "pytest", "-q", "test_labels.py"]
    if os.name == "nt":
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


@pytest.mark.asyncio
@pytest.mark.parametrize("fake_check", [False, True], ids=["actual-pytest", "fake-echo"])
async def test_python_reuse_scenario(fake_check: bool) -> None:
    pytest_command = "echo pytest 4 passed" if fake_check else get_pytest_command()

    responses = [
        [ToolCall(id="read", name="read_file", arguments={"path": "normalization.py"})],
        [
            ToolCall(
                id="write",
                name="write_file",
                arguments={"path": "label_index.py", "content": CORRECT_IMPLEMENTATION},
            )
        ],
        [
            ToolCall(
                id="check", name="shell", arguments={"command": pytest_command, "background": False}
            )
        ],
        "Done",
    ]

    provider = MockProvider(responses=responses)
    rig = EvalTestRig(provider=provider, profile="basic")

    try:
        rig.setup("reuse-positive")
        if fake_check:
            with pytest.raises(AssertionError, match="verification"):
                await run_python_reuse_scenario(rig)
        else:
            result = await run_python_reuse_scenario(rig)
            assert result.success
    finally:
        rig.cleanup()
