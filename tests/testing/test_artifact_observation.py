"""Contracts for bounded artifact snapshots shared by team evaluations."""

import hashlib
from pathlib import Path

import pytest

from henchman.core.events import AgentEvent, EventType


def test_fingerprint_hashes_file_bytes(tmp_path: Path) -> None:
    from evals.artifact_observation import fingerprint

    path = tmp_path / "source.py"
    content = b"print('hello')\n"
    path.write_bytes(content)
    assert fingerprint(path) == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize("invalid", ["missing", "directory", "symlink", "oversize"])
def test_fingerprint_rejects_unknown_artifacts(tmp_path: Path, invalid: str) -> None:
    from evals.artifact_observation import fingerprint

    path = tmp_path / "source.py"
    if invalid == "directory":
        path.mkdir()
    elif invalid == "symlink":
        target = tmp_path / "target.py"
        target.write_text("pass\n")
        path.symlink_to(target)
    elif invalid == "oversize":
        path.write_bytes(b"x" * 1_048_577)
    assert fingerprint(path) is None


def test_fingerprint_accepts_exact_size_limit(tmp_path: Path) -> None:
    from evals.artifact_observation import fingerprint

    path = tmp_path / "source.py"
    content = b"x" * 1_048_576
    path.write_bytes(content)
    assert fingerprint(path) == hashlib.sha256(content).hexdigest()


def test_timeline_tracks_nested_implementation_changes_and_protected_restore(
    tmp_path: Path,
) -> None:
    from evals.artifact_observation import ArtifactTimeline, fingerprint

    implementation = tmp_path / "src" / "package" / "caller.py"
    implementation.parent.mkdir(parents=True)
    implementation.write_text("before\n")
    protected = tmp_path / "tests.py"
    protected.write_text("original\n")
    initial = {
        "src/package/caller.py": fingerprint(implementation),
        "tests.py": fingerprint(protected),
    }
    timeline = ArtifactTimeline(
        tmp_path,
        initial,
        implementation_paths=("src/package/caller.py",),
        protected_paths=("tests.py",),
    )
    event = AgentEvent(EventType.CONTENT, "Observed state")
    timeline(event)
    (tmp_path / "untracked.txt").write_text("ignored\n")
    implementation.write_text("after\n")
    timeline(event)
    protected.write_text("mutated\n")
    timeline(event)
    protected.write_text("original\n")
    timeline(event)
    assert timeline.finish(4) == {
        "complete": True,
        "events_observed": 4,
        "first_implementation_change": 1,
        "last_implementation_change": 1,
        "protected_change_observed": True,
        "snapshot_errors": [],
    }


def test_finish_catches_change_after_last_event(tmp_path: Path) -> None:
    from evals.artifact_observation import ArtifactTimeline, fingerprint

    path = tmp_path / "caller.py"
    path.write_text("before\n")
    timeline = ArtifactTimeline(
        tmp_path,
        {"caller.py": fingerprint(path)},
        implementation_paths=("caller.py",),
        protected_paths=(),
    )
    timeline(AgentEvent(EventType.FINISHED))
    path.write_text("after\n")
    observation = timeline.finish(1)
    assert observation["complete"]
    assert observation["first_implementation_change"] == 1
    assert observation["last_implementation_change"] == 1


def test_missing_event_callback_fails_closed(tmp_path: Path) -> None:
    from evals.artifact_observation import ArtifactTimeline

    timeline = ArtifactTimeline(tmp_path, {}, implementation_paths=(), protected_paths=())
    assert not timeline.finish(1)["complete"]


def test_initial_unknown_snapshot_remains_incomplete_after_recovery(tmp_path: Path) -> None:
    from evals.artifact_observation import ArtifactTimeline

    timeline = ArtifactTimeline(
        tmp_path,
        {"caller.py": None},
        implementation_paths=("caller.py",),
        protected_paths=(),
    )
    (tmp_path / "caller.py").write_text("recovered\n")
    observation = timeline.finish(0)
    assert not observation["complete"]
    assert observation["snapshot_errors"] == ["caller.py"]


def test_injected_fingerprint_preserves_transient_unknown_snapshot(tmp_path: Path) -> None:
    from evals.artifact_observation import ArtifactTimeline

    values = iter([None, "initial"])
    observed_paths: list[Path] = []

    def observe(path: Path) -> str | None:
        observed_paths.append(path)
        return next(values)

    initial: dict[str, str | None] = {"caller.py": "initial"}
    timeline = ArtifactTimeline(
        tmp_path,
        initial,
        implementation_paths=("caller.py",),
        protected_paths=(),
        fingerprint=observe,
    )
    initial["caller.py"] = "caller changed the dictionary"
    timeline(AgentEvent(EventType.CONTENT))
    observation = timeline.finish(1)
    assert not observation["complete"]
    assert observation["snapshot_errors"] == ["caller.py"]
    assert observed_paths == [tmp_path / "caller.py"] * 2


def test_tool_target_resolves_workspace_paths_and_rejects_escapes(tmp_path: Path) -> None:
    from evals.artifact_observation import tool_target
    from evals.models import ToolLog

    cases: list[tuple[object, str | None]] = [
        ("src/package/cli.py", "src/package/cli.py"),
        (str(tmp_path / "src/package/cli.py"), "src/package/cli.py"),
        ("src/../cli.py", "cli.py"),
        ("../outside.py", None),
        (None, None),
        (23, None),
    ]
    for raw, expected in cases:
        log = ToolLog(tool_name="read_file", arguments={"path": raw}, result="", success=True)
        assert tool_target(log, tmp_path) == expected
