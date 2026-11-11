"""Operation recovery is an explicit typed policy independent of usage storage."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.schema import Settings


def test_operation_policy_defaults_to_process_and_does_not_follow_usage() -> None:
    assert Settings().operations.persistence == "process"
    assert Settings(usage={"persistence": "durable"}).operations.persistence == "process"
    settings = Settings.model_validate({"operations": {"persistence": "durable"}})
    assert settings.usage.persistence == "process"
    assert settings.model_dump()["operations"] == {"persistence": "durable"}


@pytest.mark.parametrize("value", ["off", "sqlite", True, None])
def test_invalid_operation_policy_is_not_silently_ignored(value: object) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"operations": {"persistence": value}})


def test_repository_can_enable_operation_recovery_in_canonical_project_config(tmp_path: Path) -> None:
    repository = SettingsRepository(project_root=tmp_path)
    repository.set("operations.persistence", "durable", scope=SettingsScope.PROJECT)
    assert (tmp_path / ".henchman" / "settings.yaml").exists()
    assert repository.get("operations.persistence") == "durable"
