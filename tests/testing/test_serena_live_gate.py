"""The default test suite must not install Serena from the network."""

import subprocess
from pathlib import Path
from runpy import run_path
from typing import Any

import pytest


@pytest.fixture
def serena_test() -> Any:
    module = run_path(str(Path(__file__).parents[1] / "e2e" / "test_serena_cli_integration.py"))
    return module["TestSerenaCliIntegration"]().test_real_serena_installation


def test_live_serena_is_opt_in(monkeypatch: pytest.MonkeyPatch, serena_test: Any) -> None:
    monkeypatch.delenv("HENCHMAN_RUN_LIVE_SERENA", raising=False)

    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        pytest.fail("Default suite attempted an external Serena process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    with pytest.raises(pytest.skip.Exception, match="HENCHMAN_RUN_LIVE_SERENA"):
        serena_test()


@pytest.mark.parametrize("returncode", [0, 1])
def test_opted_in_serena_preserves_outcome(
    monkeypatch: pytest.MonkeyPatch, serena_test: Any, returncode: int,
) -> None:
    monkeypatch.setenv("HENCHMAN_RUN_LIVE_SERENA", "1")
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command == ["uv", "--version"]:
            return subprocess.CompletedProcess(command, 0, "uv test", "")
        return subprocess.CompletedProcess(command, returncode, "Usage: serena", "build failed")

    monkeypatch.setattr(subprocess, "run", run)
    if returncode:
        with pytest.raises(AssertionError, match="build failed"):
            serena_test()
    else:
        serena_test()
    assert commands == [
        ["uv", "--version"],
        ["uvx", "--from", "git+https://github.com/oraios/serena", "serena", "--help"],
    ]
