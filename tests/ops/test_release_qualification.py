"""Publication requires checks of the exact wheel and source archive."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from unittest.mock import Mock

import pytest
from tests.ops.test_release import COMMIT, _distributions

from henchman.ops import release


def candidate(root: Path) -> Path:
    dist = root / "dist"
    dist.mkdir()
    _distributions(dist)
    helper = root / "tests/testing/installed_wheel_smoke.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("# fixture smoke implementation\n")
    return dist


def fake_runner(root: Path, *, fail: str | None = None, mutate: bool = False):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] != root
        assert "PYPI" not in kwargs["env"]
        assert kwargs["timeout"] > 0
        if command[:2] == ["uv", "build"]:
            assert command[-1] == str((root / "dist/henchman_ai-0.4.1.tar.gz").resolve())
            output = Path(command[command.index("--out-dir") + 1])
            output.mkdir()
            shutil.copyfile(root / "dist/henchman_ai-0.4.1-py3-none-any.whl",
                            output / "henchman_ai-0.4.1-py3-none-any.whl")
        if "installed_wheel_smoke.py" in " ".join(command):
            mode = "sdist" if "sdist" in command[0] else "wheel"
            if mode == fail:
                raise subprocess.CalledProcessError(1, command)
            if mode == "sdist" and mutate:
                with (root / "dist/henchman_ai-0.4.1-py3-none-any.whl").open("ab") as stream:
                    stream.write(b"changed after verification")
        return Mock(returncode=0)

    return run, calls


def test_missing_qualification_blocks_publisher_before_credentials(tmp_path, monkeypatch):
    dist = candidate(tmp_path)
    monkeypatch.setenv("RELEASE_SHA", COMMIT)
    runner = Mock()
    monkeypatch.setattr(release.subprocess, "run", runner)
    with pytest.raises(ValueError, match="qualification"):
        release.publish(dist, "0.4.1")
    runner.assert_not_called()


def test_both_artifacts_are_checked_in_distinct_clean_environments(tmp_path, monkeypatch):
    dist = candidate(tmp_path)
    runner, calls = fake_runner(tmp_path)
    monkeypatch.setattr(release, "_qualification_step", runner)
    release.qualify_distributions(tmp_path, "0.4.1", COMMIT)
    record = release.validate_qualification(dist, "0.4.1", COMMIT)
    runs = [call for call in calls if "installed_wheel_smoke.py" in " ".join(call)]
    assert len(runs) == 2
    assert runs[0][0] != runs[1][0]
    assert all("--wheel-dir" in call for call in runs)
    assert all("--include-package" in call for call in runs)
    assert set(record["runs"]) == {"wheel", "sdist"}
    for path in dist.iterdir():
        assert record["artifacts"][path.name] == hashlib.sha256(path.read_bytes()).hexdigest()

    publisher = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(release.subprocess, "run", publisher)
    monkeypatch.setenv("RELEASE_SHA", COMMIT)
    monkeypatch.setenv("PYPI", "[pypi]\npassword=pypi-fixture")
    assert release.publish(dist, "0.4.1") == 0
    assert publisher.call_args.args[0][:2] == ["uv", "publish"]


@pytest.mark.parametrize("failed", ["wheel", "sdist"])
def test_failed_check_invalidates_previous_receipt(tmp_path, monkeypatch, failed):
    candidate(tmp_path)
    receipt = tmp_path / "release-evidence/qualification.json"
    receipt.parent.mkdir()
    receipt.write_text("old result")
    runner, _calls = fake_runner(tmp_path, fail=failed)
    monkeypatch.setattr(release, "_qualification_step", runner)
    with pytest.raises(ValueError, match="qualification"):
        release.qualify_distributions(tmp_path, "0.4.1", COMMIT)
    assert not receipt.exists()


def test_mutation_during_qualification_cannot_create_receipt(tmp_path, monkeypatch):
    candidate(tmp_path)
    runner, _calls = fake_runner(tmp_path, mutate=True)
    monkeypatch.setattr(release, "_qualification_step", runner)
    with pytest.raises(ValueError, match="changed"):
        release.qualify_distributions(tmp_path, "0.4.1", COMMIT)
    assert not (tmp_path / "release-evidence/qualification.json").exists()


@pytest.mark.parametrize("change", ["wheel", "sdist", "commit", "version", "failed", "missing-run", "helper"])
def test_mismatched_or_incomplete_receipt_blocks_publish(tmp_path, monkeypatch, change):
    dist = candidate(tmp_path)
    runner, _calls = fake_runner(tmp_path)
    monkeypatch.setattr(release, "_qualification_step", runner)
    release.qualify_distributions(tmp_path, "0.4.1", COMMIT)
    receipt = tmp_path / "release-evidence/qualification.json"
    data = json.loads(receipt.read_text())
    if change in {"wheel", "sdist"}:
        suffix = ".whl" if change == "wheel" else ".tar.gz"
        data["artifacts"][next(name for name in data["artifacts"] if name.endswith(suffix))] = "0" * 64
    elif change == "commit":
        data["commit"] = "b" * 40
    elif change == "version":
        data["version"] = "0.0.0"
    elif change == "failed":
        data["runs"]["sdist"]["passed"] = False
    elif change == "helper":
        (tmp_path / "tests/testing/installed_wheel_smoke.py").write_text("changed checks")
    else:
        del data["runs"]["sdist"]
    receipt.write_text(json.dumps(data))
    publisher = Mock()
    monkeypatch.setattr(release.subprocess, "run", publisher)
    monkeypatch.setenv("RELEASE_SHA", COMMIT)
    with pytest.raises(ValueError, match="qualification"):
        release.publish(dist, "0.4.1")
    publisher.assert_not_called()


@pytest.mark.skipif(sys.platform != "linux", reason="Owned descendant reaping uses Linux subreaper")
def test_timeout_stops_helper_descendants_before_returning(tmp_path):
    import ctypes
    import signal

    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    marker, pid_file = tmp_path / "late-effect", tmp_path / "child.pid"
    child = 'import pathlib,sys,time;time.sleep(.6);pathlib.Path(sys.argv[1]).write_text("late");time.sleep(30)'
    parent = ('import pathlib,subprocess,sys,time;p=subprocess.Popen([sys.executable,"-c",sys.argv[1],sys.argv[2]]);'
              'pathlib.Path(sys.argv[3]).write_text(str(p.pid));time.sleep(30)')
    try:
        with (tmp_path / "process.log").open("wb") as log, pytest.raises(subprocess.TimeoutExpired):
            release._qualification_step([sys.executable, "-c", parent, child, str(marker), str(pid_file)],
                                        cwd=tmp_path, env=dict(os.environ), stdout=log, timeout=0.3)
        assert pid_file.exists(), "fixture must spawn its child before the timeout"
        time.sleep(.7)
        assert not marker.exists(), "descendant executed after failed qualification"
    finally:
        if pid_file.exists():
            pid = int(pid_file.read_text())
            with suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
        assert libc.prctl(36, previous.value, 0, 0, 0) == 0
