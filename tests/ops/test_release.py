"""Release credential, version, and upload boundaries."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from henchman.ops.release import parse_pypi_token, publish, validate_release


@pytest.mark.parametrize("username", ["__token__", "**token**"])
def test_config_fragment_extracts_password_without_interpolation(username: str) -> None:
    token = "pypi-example%with-percent"
    assert parse_pypi_token(f"[pypi]\nusername = {username}\npassword = {token}\n") == token


@pytest.mark.parametrize(
    "fragment",
    [
        "",
        "pypi-secret",
        "[other]\npassword=pypi-secret",
        "[pypi]\nusername=__token__",
        "[pypi]\nusername=person\npassword=pypi-secret",
        "[pypi]\npassword=wrong-secret",
        "[pypi]\npassword=pypi-secret\npassword=pypi-other",
    ],
)
def test_invalid_credentials_fail_without_disclosing_input(fragment: str) -> None:
    with pytest.raises(ValueError) as error:
        parse_pypi_token(fragment)
    assert "secret" not in str(error.value)
    assert "PYPI" in str(error.value)


def _project(root: Path, metadata: str = "0.4.1", runtime: str = "0.4.1") -> None:
    (root / "pyproject.toml").write_text(f'[project]\nversion = "{metadata}"\n')
    package = root / "src/henchman"
    package.mkdir(parents=True)
    (package / "version.py").write_text(f'VERSION = "{runtime}"\n')


def test_milestone_version_must_match_both_source_versions(tmp_path: Path) -> None:
    _project(tmp_path)
    assert validate_release(tmp_path, "v0.4.1") == "0.4.1"


@pytest.mark.parametrize("milestone", ["", "release", "v0.4.1;echo bad", "v0.4.2"])
def test_invalid_or_mismatched_milestone_blocks_release(tmp_path: Path, milestone: str) -> None:
    _project(tmp_path)
    with pytest.raises(ValueError):
        validate_release(tmp_path, milestone)


def test_runtime_mismatch_blocks_release(tmp_path: Path) -> None:
    _project(tmp_path, runtime="0.4.0")
    with pytest.raises(ValueError, match="version"):
        validate_release(tmp_path, "v0.4.1")


def test_upload_uses_child_environment_and_propagates_failure(tmp_path: Path, monkeypatch) -> None:
    for filename in ("henchman_ai-0.4.1-py3-none-any.whl", "henchman_ai-0.4.1.tar.gz"):
        (tmp_path / filename).touch()
    monkeypatch.setenv("PYPI", "[pypi]\nusername=**token**\npassword=pypi-example")
    runner = Mock(return_value=Mock(returncode=17))
    monkeypatch.setattr("henchman.ops.release.subprocess.run", runner)
    assert publish(tmp_path, "0.4.1") == 17
    command = runner.call_args.args[0]
    environment = runner.call_args.kwargs["env"]
    assert command[:2] == ["uv", "publish"]
    assert "--check-url" in command
    assert "pypi-example" not in command
    assert environment["UV_PUBLISH_TOKEN"] == "pypi-example"
    assert "PYPI" not in environment


def test_missing_distribution_blocks_upload(tmp_path: Path, monkeypatch) -> None:
    runner = Mock()
    monkeypatch.setattr("henchman.ops.release.subprocess.run", runner)
    with pytest.raises(ValueError, match="distribution"):
        publish(tmp_path, "0.4.1")
    runner.assert_not_called()
