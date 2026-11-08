"""Nonsecret operational transfer requires explicit intent and preserves meaning."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from henchman.config.repository import SettingsRepository, SettingsScope
from henchman.config.settings import load_settings_snapshot

CONTROLS = {
    "usage": {
        "limits": {
            "max_requests": 0,
            "max_tokens": 17,
            "max_seconds": 0.0,
            "max_cost": "1E-21",
            "currency": "USD",
        },
        "prices": [
            {
                "provider": "local",
                "model": "fixture",
                "input_per_1k": "0",
                "output_per_1k": "0.123456789012345678901",
                "source": "configured",
                "currency": "USD",
                "as_of": "2026-11-07",
            }
        ],
        "persistence": "durable",
    },
    "operations": {"persistence": "durable"},
    "verification": {
        "checks": [
            {
                "kind": "command",
                "argv": ["python", "-m", "pytest"],
                "inputs": ["tests/test_app.py"],
                "timeout": 7,
                "requirement_ids": ["unit"],
            }
        ]
    },
}


def write(root: Path, values: dict) -> Path:
    path = root / ".henchman" / "settings.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(values), encoding="utf-8")
    return path


@pytest.mark.parametrize("scope", [SettingsScope.GLOBAL, SettingsScope.PROJECT])
def test_opted_in_control_roundtrip_preserves_precision_and_explicit_defaults(
    tmp_path, scope
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    write(
        source,
        {
            **CONTROLS,
            "ui": {"theme": "light"},
            "providers": {"deepseek": {"api_key": "hidden-secret"}},
        },
    )
    source_repo = SettingsRepository(source)
    assert source_repo.export_settings(scope=SettingsScope.PROJECT) == {"ui": {"theme": "light"}}
    exported = source_repo.export_settings(scope=SettingsScope.PROJECT, include_controls=True)
    assert exported == {**CONTROLS, "ui": {"theme": "light"}}
    assert Decimal(exported["usage"]["limits"]["max_cost"]) == Decimal("0.000000000000000000001")
    original = deepcopy(exported)
    target = SettingsRepository(destination)
    target.import_settings(exported, scope=scope, accept_control_changes=True)
    assert target.export_settings(scope=scope, include_controls=True) == original
    assert exported == original
    assert "providers" not in exported


@pytest.mark.parametrize(
    "payload",
    [
        {"usage": {"limits": {"max_requests": None}}},
        {"usage": {"limits": {"max_requests": 100}}},
        {"usage": {"limits": {"currency": "EUR", "max_cost": "1"}}},
        {"usage": {"prices": []}},
        {"usage": {"persistence": "process"}},
        {"operations": {"persistence": "process"}},
        {"verification": {"checks": []}},
    ],
)
def test_control_mutations_require_explicit_acceptance_without_partial_ui_write(
    tmp_path, payload
) -> None:
    path = write(tmp_path, {**CONTROLS, "ui": {"theme": "dark"}})
    original = path.read_bytes()
    with pytest.raises(ValueError, match="accept-control-changes"):
        SettingsRepository(tmp_path).import_settings(
            {"ui": {"theme": "light"}, **payload}, scope=SettingsScope.PROJECT
        )
    assert path.read_bytes() == original


def test_supplied_mapping_leaves_merge_but_lists_replace(tmp_path) -> None:
    write(tmp_path, CONTROLS)
    repository = SettingsRepository(tmp_path)
    payload = {
        "usage": {"limits": {"max_tokens": None}, "prices": []},
        "verification": {"checks": []},
    }
    repository.import_settings(payload, scope=SettingsScope.PROJECT, accept_control_changes=True)
    current = repository.view(scope=SettingsScope.PROJECT)
    assert current["usage"]["limits"] == {**CONTROLS["usage"]["limits"], "max_tokens": None}
    assert current["usage"]["prices"] == []
    assert current["usage"]["persistence"] == "durable"
    assert current["operations"] == CONTROLS["operations"]
    assert current["verification"]["checks"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {"providers": {"deepseek": {"api_key": "credential"}}},
        {"tools": {"auto_approve_read": True}},
        {"accept_control_changes": True},
        {"usage": {"limits": {"max_requests": -1}}},
        {"usage": {"limits": {"max_tokens": True}}},
        {"usage": {"limits": {"max_cost": "NaN"}}},
        {"usage": {"prices": [{"provider": "x", "model": "y", "api_key": "credential"}]}},
        {"operations": {"persistence": "unsafe"}},
        {
            "verification": {
                "checks": [{"kind": "file_changed", "path": "x.py", "baseline_captured": True}]
            }
        },
        {"verification": {"checks": [{"kind": "command", "argv": "rm -rf"}]}},
    ],
)
def test_invalid_or_out_of_scope_transfer_is_atomic_even_with_acceptance(tmp_path, payload) -> None:
    path = write(tmp_path, {"ui": {"theme": "dark"}})
    original = path.read_bytes()
    with pytest.raises(ValueError):
        SettingsRepository(tmp_path).import_settings(
            payload, scope=SettingsScope.PROJECT, accept_control_changes=True
        )
    assert path.read_bytes() == original


@pytest.mark.parametrize("location", ["source", "model", "argv", "path"])
@pytest.mark.parametrize("secret", ["private-canary", "q", 'quote"\\canary'])
def test_known_operational_credentials_reject_lossy_export_and_import(
    tmp_path, location, secret
) -> None:
    payload = deepcopy(CONTROLS)
    if location in {"source", "model"}:
        payload["usage"]["prices"][0][location] = f"prefix-{secret}-suffix"
    elif location == "argv":
        payload["verification"]["checks"][0]["argv"].append(f"--value={secret}")
    else:
        payload["verification"]["checks"] = [
            {"kind": "file_contains", "path": "x.py", "text": secret}
        ]
    write(tmp_path, {**payload, "providers": {"deepseek": {"api_key": secret}}})
    repository = SettingsRepository(tmp_path)
    original = repository.view(scope=SettingsScope.PROJECT)
    with pytest.raises(ValueError, match="credential"):
        repository.export_settings(scope=SettingsScope.PROJECT, include_controls=True)
    with pytest.raises(ValueError, match="credential"):
        repository.import_settings(
            payload, scope=SettingsScope.PROJECT, accept_control_changes=True
        )
    assert repository.view(scope=SettingsScope.PROJECT) == original


def test_retained_policy_remembers_rotated_and_explicit_credentials(tmp_path) -> None:
    path = write(tmp_path, {"providers": {"deepseek": {"api_key": "old-private"}}})
    repository = SettingsRepository(tmp_path)
    repository.evidence_redactor().register_secret("explicit-private")
    write(
        tmp_path,
        {
            "providers": {"deepseek": {"api_key": "new-private"}},
            "usage": {
                "prices": [
                    {
                        "provider": "local",
                        "model": "fixture",
                        "source": "old-private explicit-private",
                    }
                ]
            },
        },
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="credential"):
        repository.export_settings(scope=SettingsScope.PROJECT, include_controls=True)
    assert path.read_bytes() == before


def test_unknown_auth_header_in_check_is_refused_without_executable_placeholder(tmp_path) -> None:
    payload = {
        "verification": {
            "checks": [
                {"kind": "command", "argv": ["curl", "-H", "Authorization: Bearer hidden-header"]}
            ]
        }
    }
    repository = SettingsRepository(tmp_path)
    with pytest.raises(ValueError, match="credential"):
        repository.import_settings(
            payload, scope=SettingsScope.PROJECT, accept_control_changes=True
        )
    assert not (tmp_path / ".henchman").exists()


def test_fixed_numeric_and_enum_meaning_survives_short_credential_policy(tmp_path) -> None:
    write(
        tmp_path,
        {
            "providers": {"deepseek": {"api_key": "0"}},
            "usage": {"limits": {"max_cost": "0", "currency": "USD"}, "persistence": "process"},
            "operations": {"persistence": "durable"},
        },
    )
    exported = SettingsRepository(tmp_path).export_settings(
        scope=SettingsScope.PROJECT, include_controls=True
    )
    assert exported["usage"]["limits"]["max_cost"] == "0"
    assert exported["usage"]["persistence"] == "process"


def test_import_targets_canonical_project_preserves_layers_and_session_origin(tmp_path, monkeypatch) -> None:
    write(Path.home(), {"usage": {"limits": {"max_requests": 9, "max_tokens": 100}}})
    legacy = tmp_path / ".Henchman"
    legacy.mkdir()
    (legacy / "settings.yaml").write_text(yaml.safe_dump({"ui": {"theme": "light"}}))
    before = (legacy / "settings.yaml").read_bytes()
    canonical_file = tmp_path / ".henchman" / "settings.yaml"
    same_directory = canonical_file.exists() and canonical_file.samefile(legacy / "settings.yaml")
    destinations: list[Path] = []
    replace = Path.replace

    def observe_replace(source: Path, target: Path) -> Path:
        destinations.append(target)
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", observe_replace)
    repository = SettingsRepository(tmp_path)
    repository.import_settings(
        {"usage": {"limits": {"max_requests": 0}}},
        scope=SettingsScope.PROJECT,
        accept_control_changes=True,
    )
    snapshot = load_settings_snapshot(tmp_path, overrides={"usage": {"limits": {"max_tokens": 2}}})
    assert snapshot.settings.usage.limits.max_requests == 0
    assert snapshot.settings.usage.limits.max_tokens == 2
    assert snapshot.origins["usage.limits.max_requests"].scope == "project"
    assert snapshot.origins["usage.limits.max_tokens"].scope == "session"
    saved = repository.view(scope=SettingsScope.PROJECT)
    assert saved["usage"] == {"limits": {"max_requests": 0}}
    assert [str(path) for path in destinations] == [str(canonical_file)]
    if same_directory:
        # Case-insensitive filesystems expose one file through both spellings.
        assert (legacy / "settings.yaml").samefile(canonical_file)
        assert saved["ui"]["theme"] == "light"
    else:
        assert (legacy / "settings.yaml").read_bytes() == before


def test_real_replace_error_is_preserved_and_existing_document_unchanged(
    tmp_path, monkeypatch
) -> None:
    path = write(tmp_path, {"ui": {"theme": "dark"}})
    before = path.read_bytes()
    failure = OSError("owned replace failure")

    def refuse(*_args):
        raise failure

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError) as caught:
        SettingsRepository(tmp_path).import_settings(
            CONTROLS, scope=SettingsScope.PROJECT, accept_control_changes=True
        )
    assert caught.value is failure
    assert path.read_bytes() == before


@pytest.mark.parametrize("acceptance", [1, "true", [True]])
def test_control_acceptance_is_an_exact_boolean(tmp_path, acceptance) -> None:
    with pytest.raises(ValueError, match="accept-control-changes"):
        SettingsRepository(tmp_path).import_settings(
            {"operations": {"persistence": "process"}},
            scope=SettingsScope.PROJECT,
            accept_control_changes=acceptance,
        )
    assert not (tmp_path / ".henchman").exists()


def test_partial_export_and_import_do_not_materialize_unrelated_defaults(tmp_path) -> None:
    write(tmp_path, {"usage": {"limits": {"max_requests": 0}}})
    repository = SettingsRepository(tmp_path)
    exported = repository.export_settings(scope=SettingsScope.PROJECT, include_controls=True)
    assert exported == {"usage": {"limits": {"max_requests": 0}}}
    destination = SettingsRepository(tmp_path / "destination")
    destination.import_settings(exported, scope=SettingsScope.PROJECT, accept_control_changes=True)
    assert destination.view(scope=SettingsScope.PROJECT) == exported


def test_transfer_obeys_explicit_file_and_session_precedence_without_persisting_them(
    tmp_path, monkeypatch
) -> None:
    explicit = tmp_path / "selected.yaml"
    explicit.write_text(
        yaml.safe_dump({"usage": {"limits": {"max_requests": 7, "max_tokens": 19}}})
    )
    monkeypatch.setenv("HENCHMAN_SETTINGS_PATH", str(explicit))
    repository = SettingsRepository(tmp_path)
    repository.import_settings(
        {"usage": {"limits": {"max_requests": 0}}},
        scope=SettingsScope.PROJECT,
        accept_control_changes=True,
    )
    snapshot = load_settings_snapshot(tmp_path, overrides={"usage": {"limits": {"max_tokens": 2}}})
    assert snapshot.settings.usage.limits.max_requests == 7
    assert snapshot.origins["usage.limits.max_requests"].scope == "file"
    assert snapshot.settings.usage.limits.max_tokens == 2
    assert snapshot.origins["usage.limits.max_tokens"].scope == "session"
    assert repository.view(scope=SettingsScope.PROJECT) == {
        "usage": {"limits": {"max_requests": 0}}
    }


def test_effective_runtime_credential_refuses_operational_export(tmp_path) -> None:
    from henchman.config.schema import Settings
    from henchman.config.settings import SettingsSnapshot

    secret = "only-in-held-runtime-policy"
    write(
        tmp_path,
        {"usage": {"prices": [{"provider": "local", "model": "fixture", "source": secret}]}},
    )
    held = Settings(providers={"deepseek": {"api_key": secret}})
    repository = SettingsRepository(tmp_path, snapshot_provider=lambda: SettingsSnapshot(held, {}))
    with pytest.raises(ValueError, match="credential"):
        repository.export_settings(scope=SettingsScope.PROJECT, include_controls=True)
    assert held.providers.deepseek["api_key"] == secret


@pytest.mark.parametrize("credential", ["USD", "durable", "command"])
def test_verified_protocol_identities_remain_exact(tmp_path, credential) -> None:
    controls = {
        "usage": {"limits": {"currency": "USD", "max_cost": "0"}},
        "operations": {"persistence": "durable"},
        "verification": {"checks": [{"kind": "command", "argv": ["python"]}]},
    }
    write(tmp_path, {**controls, "providers": {"deepseek": {"api_key": credential}}})
    assert (
        SettingsRepository(tmp_path).export_settings(
            scope=SettingsScope.PROJECT, include_controls=True
        )
        == controls
    )


def test_export_refuses_operational_redaction_learned_during_final_projection(
    tmp_path, monkeypatch
) -> None:
    secret = "late-known-control-source"
    write(
        tmp_path,
        {
            "ui": {"theme": "light"},
            "usage": {"prices": [{"provider": "local", "model": "fixture", "source": secret}]},
        },
    )
    repository = SettingsRepository(tmp_path)
    policy = repository.evidence_redactor()
    original = policy.redact

    def learn_from_final_ui(value, *, schema=None):
        if isinstance(value, dict) and "ui" in value:
            policy.register_secret(secret)
        return original(value, schema=schema)

    monkeypatch.setattr(policy, "redact", learn_from_final_ui)
    with pytest.raises(ValueError, match="credential"):
        repository.export_settings(scope=SettingsScope.PROJECT, include_controls=True)
    assert repository.view(scope=SettingsScope.PROJECT)["usage"]["prices"][0]["source"] == secret


def test_explicit_default_controls_override_lower_scope_without_being_dropped(tmp_path) -> None:
    write(
        Path.home(),
        {
            "usage": {"limits": {"max_requests": 1}, "persistence": "durable"},
            "operations": {"persistence": "durable"},
        },
    )
    payload = {
        "usage": {"limits": {"max_requests": None}, "persistence": "process"},
        "operations": {"persistence": "process"},
    }
    repository = SettingsRepository(tmp_path)
    repository.import_settings(payload, scope=SettingsScope.PROJECT, accept_control_changes=True)
    assert repository.view(scope=SettingsScope.PROJECT) == payload
    snapshot = load_settings_snapshot(tmp_path)
    assert snapshot.settings.usage.limits.max_requests is None
    assert snapshot.settings.usage.persistence == "process"
    assert snapshot.settings.operations.persistence == "process"
    assert snapshot.origins["usage.persistence"].scope == "project"
