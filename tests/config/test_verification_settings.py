"""Explicit check configuration shares the existing bounded assertion contract."""

import pytest
from pydantic import ValidationError

from henchman.config.schema import Settings


def test_verification_defaults_do_not_require_commands():
    assert Settings().verification.checks == []


def test_verification_configuration_keeps_exact_argv_and_requirements():
    check = {"kind": "command", "argv": ["python", "-c", "print('hello world')"],
             "inputs": ["source.py"], "requirement_ids": ["REQ-1"]}
    settings = Settings.model_validate({"verification": {"checks": [check]}})
    assert settings.verification.checks == [check]


@pytest.mark.parametrize("checks", [
    [{"kind": "pytest", "path": "../outside"}],
    [{"kind": "command", "argv": "python -m pytest"}],
    [{"kind": "file_changed", "path": "source.py", "baseline_sha256": "a" * 64}],
    [{"kind": "file_exists", "path": "source.py", "requirement_ids": ["not a stable id"]}],
    [{"kind": "file_exists", "path": "source.py"}] * 21,
])
def test_invalid_project_checks_fail_settings_validation(checks):
    with pytest.raises(ValidationError):
        Settings.model_validate({"verification": {"checks": checks}})
