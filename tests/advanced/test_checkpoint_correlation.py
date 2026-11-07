"""Checkpoint operation correlation is typed, bounded and advisory."""

import json
from dataclasses import asdict

import pytest

from henchman.advanced.checkpoints import CheckpointService


def test_optional_typed_correlation_survives_review_and_old_records(tmp_path):
    from henchman.advanced.checkpoint_models import CheckpointOperation

    operation = CheckpointOperation("operation", "run", "agent", "tool")
    service = CheckpointService(tmp_path)
    record = service.begin(["file"], actor="agent", operation=operation)
    service.complete(record.checkpoint_id)
    assert service.list_checkpoints()[0].operation == operation
    assert service.review(record.checkpoint_id).operation == operation
    payload_path = service._store.path / f"{record.checkpoint_id}.json"
    payload = json.loads(payload_path.read_text())
    assert payload["operation"] == asdict(operation)
    del payload["operation"]
    payload_path.write_text(json.dumps(payload))
    assert service.list_checkpoints()[0].operation is None


@pytest.mark.parametrize("invalid", ["", "x" * 257, "bad\nidentity", {}, None])
def test_invalid_correlation_never_becomes_persisted_authority(invalid):
    from henchman.advanced.checkpoint_models import CheckpointOperation

    with pytest.raises(ValueError, match="correlation"):
        CheckpointOperation(invalid, "run", "agent", "tool")
