"""Builtin role overrides inherit presets without relaxing custom-role validation."""

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from henchman.agents import presets
from henchman.config import load_settings
from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.schema import AgentConfig, AgentSettings, Settings


@pytest.mark.parametrize("role", ["tech_lead", "planner", "explorer", "engineer", "data_engineer"])
def test_partial_builtin_role_inherits_canonical_fields(role: str) -> None:
    expected = presets.get_default_team()[role].model_dump()
    overrides = {
        "model": "selected/model",
        "provider": "openrouter",
        "system_prompt": "Use project conventions",
    }
    settings = Settings.model_validate({"agents": {"agents": {role: overrides}}})
    assert settings.agents.agents[role].model_dump() == {**expected, **overrides}


def test_explicit_lists_replace_preset_scope_and_empty_prompt_is_retained() -> None:
    settings = AgentSettings.model_validate(
        {
            "agents": {
                "tech_lead": {
                    "tools": ["read_file"],
                    "auto_approve": ["read_file"],
                    "can_delegate_to": [],
                    "system_prompt": "",
                }
            }
        }
    )
    leader = settings.agents["tech_lead"]
    assert leader.tools == ["read_file"]
    assert leader.auto_approve == ["read_file"]
    assert leader.can_delegate_to == []
    assert leader.system_prompt == ""


@pytest.mark.parametrize("override", [{"tools": []}, {"tools": None}, {"model": ["bad"]}])
def test_partial_builtin_override_still_validates_explicit_values(override: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AgentSettings.model_validate({"agents": {"tech_lead": override}})


def test_unknown_custom_role_still_requires_metadata() -> None:
    with pytest.raises(ValidationError) as failure:
        AgentSettings.model_validate({"agents": {"custom": {"model": "selected"}}})
    missing = {error["loc"][-1] for error in failure.value.errors() if error["type"] == "missing"}
    assert missing == {"name", "role", "description"}
    configured = AgentSettings.model_validate(
        {
            "agents": {
                "custom": {
                    "name": "Custom",
                    "role": "custom",
                    "description": "Explicit role",
                    "tools": ["read_file"],
                }
            }
        }
    )
    assert configured.agents["custom"].tools == ["read_file"]


def test_typed_agent_config_remains_explicit_and_is_not_merged() -> None:
    configured = AgentConfig(name="Explicit", role="tech_lead", description="Programmatic")
    settings = AgentSettings(agents={"tech_lead": configured})
    assert settings.agents["tech_lead"] is configured
    assert settings.agents["tech_lead"].tools == []
    assert settings.agents["tech_lead"].system_prompt is None


def test_normalization_does_not_mutate_input_or_canonical_presets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team = presets.get_default_team()
    original_presets = {role: config.model_dump() for role, config in team.items()}
    monkeypatch.setattr(presets, "get_default_team", lambda: team)
    raw = {"agents": {"tech_lead": {"model": "chosen", "tools": ["read_file"]}}}
    before = deepcopy(raw)
    settings = AgentSettings.model_validate(raw)
    settings.agents["tech_lead"].tools.append("grep")
    assert raw == before
    assert {role: config.model_dump() for role, config in team.items()} == original_presets


def test_repository_load_and_edits_preserve_partial_role_fields_and_other_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    home = tmp_path / "isolated-home"
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.delenv("HENCHMAN_SETTINGS_PATH", raising=False)
    project = tmp_path / "project"
    directory = project / ".henchman"
    directory.mkdir(parents=True)
    settings_file = directory / "settings.yaml"
    settings_file.write_text(
        yaml.safe_dump(
            {
                "agents": {"agents": {"tech_lead": {"model": "initial", "tools": ["read_file"]}}},
                "ui": {"theme": "dracula"},
            }
        ),
        encoding="utf-8",
    )
    assert load_settings(project_root=project).agents.agents["tech_lead"].model == "initial"
    repository = SettingsRepository(project_root=project)
    for field, value in (("model", "selected"), ("provider", "openrouter"), ("system_prompt", "")):
        repository.set(f"agents.agents.tech_lead.{field}", value, scope=SettingsScope.PROJECT)
    leader = load_settings(project_root=project).agents.agents["tech_lead"]
    assert (leader.model, leader.provider, leader.system_prompt) == ("selected", "openrouter", "")
    assert leader.tools == ["read_file"]
    assert repository.get("ui.theme") == "dracula"
    exported = repository.export_settings(scope=SettingsScope.PROJECT)
    repository.import_settings(exported, scope=SettingsScope.PROJECT)
    assert load_settings(project_root=project).agents.agents["tech_lead"] == leader
    assert settings_file.is_file()
    assert not (project / ".hENCHMAN").exists()
    assert not home.exists()
