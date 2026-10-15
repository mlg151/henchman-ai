"""Bounded coverage and cancellation for repository quality scans."""

import asyncio
from threading import Event

import pytest

from henchman.analysis.smells import scanner
from henchman.tools.builtins.python_ast import PythonAstTool


def test_total_byte_budget_stops_before_reading_another_file(tmp_path, monkeypatch):
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}.py").write_text("value = 1\n")
    monkeypatch.setattr(scanner, "MAX_FILE_BYTES", 10)
    monkeypatch.setattr(scanner, "MAX_TOTAL_BYTES", 15)
    report = scanner.scan_quality(str(tmp_path), scanner.ScanOptions())
    assert not report.complete
    assert report.truncated
    assert report.files_examined == 2
    assert report.bytes_read == 16  # One bounded overflow byte establishes truncation.
    assert report.files_analyzed == 1


def test_oversized_files_cannot_bypass_total_byte_budget(tmp_path, monkeypatch):
    for name in ("a", "b", "c", "d"):
        (tmp_path / f"{name}.py").write_bytes(b"#" * 100)
    monkeypatch.setattr(scanner, "MAX_FILE_BYTES", 10)
    monkeypatch.setattr(scanner, "MAX_TOTAL_BYTES", 15)
    report = scanner.scan_quality(str(tmp_path), scanner.ScanOptions())
    assert report.truncated
    assert report.files_examined == 2
    assert report.bytes_read == 16


def test_directory_entry_budget_is_independent_of_python_file_budget(tmp_path, monkeypatch):
    for number in range(5):
        (tmp_path / f"{number}.txt").touch()
    monkeypatch.setattr(scanner, "MAX_ENTRIES", 3)
    report = scanner.scan_quality(str(tmp_path), scanner.ScanOptions())
    assert report.truncated
    assert not report.complete
    assert report.files_analyzed == 0
    assert "entry budget" in report.errors[0]["message"]


def test_child_symlink_does_not_escape_scan_scope(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("broken syntax?!")
    try:
        (root / "linked.py").symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"Host cannot create test symlinks: {exc}")
    report = scanner.scan_quality(str(root), scanner.ScanOptions())
    assert report.complete
    assert report.files_analyzed == 0
    assert report.skipped_symlinks == 1


async def test_cancellation_stops_traversal_after_current_file(tmp_path, monkeypatch):
    for name in ("a", "b", "c"):
        (tmp_path / f"{name}.py").write_text("value = 1\n")
    entered, release, finished = Event(), Event(), Event()
    original_read = scanner._read_tree
    original_scan = scanner.scan_quality
    reports = []

    def paused_read(path, report):
        entered.set()
        if not release.wait(3):
            raise TimeoutError("Test did not release source read")
        return original_read(path, report)

    def observed_scan(*args):
        try:
            report = original_scan(*args)
            reports.append(report)
            return report
        finally:
            finished.set()

    monkeypatch.setattr(scanner, "_read_tree", paused_read)
    monkeypatch.setattr(scanner, "scan_quality", observed_scan)
    task = asyncio.create_task(PythonAstTool().execute(path=str(tmp_path), action="quality"))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, 2)
    assert reports[0].files_examined == 1
    assert reports[0].truncated
