"""A formatter failure cannot turn runtime control loss into model-retry data."""

import asyncio

import pytest

from henchman.core.operation_recovery import OperationRecoveryError
from henchman.core.run_budget import BudgetAccountingError
from henchman.providers.continuation import ProviderContinuationError
from henchman.tools import formatting
from henchman.tools.base import ToolResult
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.repair_scope import RepairControlError

CONTROLS = [OperationRecoveryError, BudgetAccountingError, ProviderContinuationError, RepairControlError]


@pytest.mark.parametrize("error_type", CONTROLS)
@pytest.mark.parametrize("boundary", ["before_snapshot", "body", "after_snapshot", "format", "format_after_body_error"])
async def test_formatter_preserves_control_at_every_effect_boundary(tmp_path, monkeypatch, error_type, boundary):
    target = tmp_path / "source.py"
    target.write_text("value = 0\n")
    control = error_type("control_sentinel")
    actual_snapshot = formatting._take_snapshot
    snapshots, bodies, formats = [], [], []

    async def snapshot(scope):
        snapshots.append(scope)
        if boundary == "before_snapshot" or boundary == "after_snapshot" and len(snapshots) == 2:
            raise control
        return await actual_snapshot(scope)

    async def execute():
        bodies.append(True)
        target.write_text("value=  123\n")
        if boundary == "body":
            raise control
        if boundary == "format_after_body_error":
            raise RuntimeError("ordinary tool failure")
        return ToolResult("written")

    async def format_sources(*_args, **_kwargs):
        formats.append(True)
        if boundary in {"format", "format_after_body_error"}:
            raise control

    monkeypatch.setattr(formatting, "_take_snapshot", snapshot)
    monkeypatch.setattr(formatting, "format_python_files", format_sources)
    formatter = formatting.PythonAutoFormatter()
    with pytest.raises(error_type) as caught:
        await formatter.run(WriteFileTool(), {"path": str(target)}, execute)
    assert caught.value is control
    assert len(bodies) == (0 if boundary == "before_snapshot" else 1)
    assert len(formats) == (1 if boundary in {"format", "format_after_body_error"} else 0)
    assert not formatter._lock.locked() and formatter._invocation.get() is None


@pytest.mark.parametrize("error_type", [*CONTROLS, asyncio.CancelledError])
async def test_primary_control_survives_formatter_settlement_failure(tmp_path, monkeypatch, error_type):
    target = tmp_path / "source.py"
    target.write_text("value = 0\n")
    control = error_type("original_control")

    async def execute():
        raise control

    async def close(*_args, **_kwargs):
        raise RuntimeError("secondary cleanup failure")

    monkeypatch.setattr(formatting, "_close_invocation", close)
    formatter = formatting.PythonAutoFormatter()
    with pytest.raises(error_type) as caught:
        await formatter.run(WriteFileTool(), {"path": str(target)}, execute)
    assert caught.value is control
    assert any("settlement" in note for note in caught.value.__notes__)
    assert not formatter._lock.locked() and formatter._invocation.get() is None


@pytest.mark.parametrize("error_type", [*CONTROLS, asyncio.CancelledError])
async def test_primary_control_survives_checkpoint_settlement_failure(tmp_path, monkeypatch, error_type):
    from types import SimpleNamespace

    control = error_type("original_control")

    async def execute():
        raise control

    async def finish(_primary):
        raise RuntimeError("secondary checkpoint failure")

    capture = SimpleNamespace(paths=(), claimed=False, restricted=lambda: False, finish=finish)
    monkeypatch.setattr(formatting, "current_checkpoint", lambda: capture)
    formatter = formatting.PythonAutoFormatter()
    with pytest.raises(error_type) as caught:
        await formatter.run(WriteFileTool(), {"path": str(tmp_path / "source.py")}, execute)
    assert caught.value is control
    assert any("checkpoint settlement" in note for note in caught.value.__notes__)
    assert capture.claimed
    assert not formatter._lock.locked() and formatter._invocation.get() is None
