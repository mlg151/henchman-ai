"""Bounded source traversal shared by quality analysis and formatting."""

import os
from collections.abc import Iterator
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

import pytest


@dataclass
class Report:
    entries_seen: int = 0
    skipped_symlinks: int = 0
    truncated: bool = False
    errors: list[tuple[Path, str]] = field(default_factory=list)

    def error(self, path: Path, message: str) -> None:
        self.errors.append((path, message))


def test_traversal_prunes_excluded_directories_and_preserves_order(tmp_path: Path) -> None:
    from henchman.utils.source_files import iter_python_files

    for name in ("b.py", "a.py", "ignore.txt"):
        (tmp_path / name).touch()
    for name in ("z", "c", ".venv", ".agent_tasks", "build"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "child.py").touch()
    report = Report()
    files = list(iter_python_files(tmp_path, report, Event()))
    assert [path.relative_to(tmp_path).as_posix() for path in files] == [
        "a.py",
        "b.py",
        "c/child.py",
        "z/child.py",
    ]
    assert report.entries_seen == 10
    assert not report.truncated
    assert not report.errors


def test_optional_suffixes_include_stubs_and_support_direct_file(tmp_path: Path) -> None:
    from henchman.utils.source_files import iter_python_files

    for name in ("implementation.py", "stub.pyi", "uppercase.PY", "readme.txt"):
        (tmp_path / name).touch()
    report = Report()
    suffixes = frozenset({".py", ".pyi"})
    files = list(iter_python_files(tmp_path, report, Event(), suffixes=suffixes))
    assert [path.name for path in files] == ["implementation.py", "stub.pyi"]
    assert list(iter_python_files(tmp_path / "stub.pyi", Report(), Event(), suffixes=suffixes)) == [
        tmp_path / "stub.pyi"
    ]


def test_default_suffix_rejects_direct_non_python_file(tmp_path: Path) -> None:
    from henchman.utils.source_files import iter_python_files

    path = tmp_path / "readme.txt"
    path.touch()
    report = Report()
    assert list(iter_python_files(path, report, Event())) == []
    assert report.errors == [(path, "Expected a .py file or directory")]


@pytest.mark.parametrize("skip_virtualenvs", [False, True])
def test_virtualenv_detection_precedes_directory_enumeration(
    tmp_path: Path, skip_virtualenvs: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    from henchman.utils import source_files

    (tmp_path / "main.py").touch()
    environment = tmp_path / "custom-environment"
    environment.mkdir()
    (environment / "pyvenv.cfg").write_text("home = /usr/bin\n")
    (environment / "library.py").touch()
    original_scandir = os.scandir
    scanned: list[Path] = []

    def observe_scandir(path: Path) -> AbstractContextManager[Iterator[os.DirEntry[str]]]:
        scanned.append(path)
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", observe_scandir)
    report = Report()
    files = list(
        source_files.iter_python_files(tmp_path, report, Event(), skip_virtualenvs=skip_virtualenvs)
    )
    assert [path.name for path in files] == (
        ["main.py"] if skip_virtualenvs else ["main.py", "library.py"]
    )
    assert (environment in scanned) is not skip_virtualenvs
    assert report.entries_seen == (2 if skip_virtualenvs else 4)


def test_virtualenv_root_is_not_enumerated_when_skipping(tmp_path: Path) -> None:
    from henchman.utils.source_files import iter_python_files

    (tmp_path / "pyvenv.cfg").touch()
    (tmp_path / "library.py").touch()
    report = Report()
    assert list(iter_python_files(tmp_path, report, Event(), skip_virtualenvs=True)) == []
    assert report.entries_seen == 0
    assert not report.errors


def test_child_symlinks_are_skipped_without_following_targets(tmp_path: Path) -> None:
    from henchman.utils.source_files import iter_python_files

    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.touch()
    try:
        (root / "linked.py").symlink_to(outside)
        (root / "linked-directory").symlink_to(tmp_path, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"Host cannot create test symlinks: {exc}")
    report = Report()
    assert list(iter_python_files(root, report, Event())) == []
    assert report.skipped_symlinks == 2
    assert report.entries_seen == 2


def test_cancellation_stops_before_the_next_file(tmp_path: Path) -> None:
    from henchman.utils.source_files import iter_python_files

    for name in ("a.py", "b.py"):
        (tmp_path / name).touch()
    stop = Event()
    report = Report()
    files = iter_python_files(tmp_path, report, stop)
    assert next(files) == tmp_path / "a.py"
    stop.set()
    assert list(files) == []
    assert report.entries_seen == 2


@pytest.mark.parametrize("count,expected_truncated", [(3, False), (4, True)])
def test_entry_budget_bounds_non_source_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    count: int,
    expected_truncated: bool,
) -> None:
    from henchman.utils import source_files

    for number in range(count):
        (tmp_path / f"{number}.txt").touch()
    monkeypatch.setattr(source_files, "MAX_ENTRIES", 3)
    report = Report()
    assert list(source_files.iter_python_files(tmp_path, report, Event())) == []
    assert report.truncated is expected_truncated
    assert bool(report.errors) is expected_truncated
    assert report.entries_seen == (0 if expected_truncated else 3)


def test_unreadable_directory_is_reported(tmp_path: Path) -> None:
    from henchman.utils.source_files import iter_python_files

    missing = tmp_path / "missing"
    report = Report()
    assert list(iter_python_files(missing, report, Event())) == []
    assert len(report.errors) == 1
    assert report.errors[0][0] == missing
