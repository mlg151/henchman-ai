"""Release credential, version, and upload boundaries."""

import io
import json
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from henchman.ops.release import (
    parse_pypi_token,
    prepare_provenance,
    publish,
    validate_distributions,
    validate_release,
)

COMMIT = "a" * 40


def _distributions(
    dist: Path, version: str = "0.4.1", commit: str = COMMIT, runtime: str = "0.4.1"
) -> None:
    metadata = f"Metadata-Version: 2.3\nName: henchman-ai\nVersion: {version}\n".encode()
    provenance = json.dumps({"commit": commit, "milestone": "v0.4.1", "pr": 8}).encode()
    source = f'VERSION = "{runtime}"\n'.encode()
    with zipfile.ZipFile(dist / "henchman_ai-0.4.1-py3-none-any.whl", "w") as wheel:
        wheel.writestr("henchman_ai-0.4.1.dist-info/METADATA", metadata)
        wheel.writestr("henchman/version.py", source)
        wheel.writestr("henchman/_release.json", provenance)
    with tarfile.open(dist / "henchman_ai-0.4.1.tar.gz", "w:gz") as sdist:
        for name, content in {
            "PKG-INFO": metadata,
            "src/henchman/version.py": source,
            "src/henchman/_release.json": provenance,
        }.items():
            member = tarfile.TarInfo(f"henchman_ai-0.4.1/{name}")
            member.size = len(content)
            sdist.addfile(member, io.BytesIO(content))


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
    _distributions(tmp_path)
    monkeypatch.setenv("PYPI", "[pypi]\nusername=**token**\npassword=pypi-example")
    monkeypatch.setenv("RELEASE_SHA", COMMIT)
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


def test_distributions_validate_metadata_runtime_and_commit(tmp_path: Path) -> None:
    _distributions(tmp_path)
    # uv creates this bookkeeping file in every output directory.
    (tmp_path / ".gitignore").write_text("*\n")
    assert len(validate_distributions(tmp_path, "0.4.1", COMMIT)) == 2


@pytest.mark.parametrize(
    "version,commit,runtime",
    [("0.4.0", COMMIT, "0.4.1"), ("0.4.1", "b" * 40, "0.4.1"), ("0.4.1", COMMIT, "0.4.0")],
)
def test_mismatched_artifact_contents_block_upload(
    tmp_path: Path, monkeypatch, version: str, commit: str, runtime: str
) -> None:
    _distributions(tmp_path, version, commit, runtime)
    monkeypatch.setenv("RELEASE_SHA", COMMIT)
    runner = Mock()
    monkeypatch.setattr("henchman.ops.release.subprocess.run", runner)
    with pytest.raises(ValueError):
        publish(tmp_path, "0.4.1")
    runner.assert_not_called()


def test_corrupt_artifact_is_rejected(tmp_path: Path) -> None:
    _distributions(tmp_path)
    (tmp_path / "henchman_ai-0.4.1.tar.gz").write_bytes(b"broken archive")
    with pytest.raises(ValueError, match="distribution"):
        validate_distributions(tmp_path, "0.4.1", COMMIT)


def test_provenance_binds_distributions_to_the_tested_commit(tmp_path: Path) -> None:
    _project(tmp_path)
    prepare_provenance(tmp_path, "0.4.1", COMMIT, "8")
    path = tmp_path / "src/henchman/_release.json"
    first = path.read_bytes()
    assert json.loads(first) == {"commit": COMMIT, "milestone": "v0.4.1", "pr": 8}
    prepare_provenance(tmp_path, "0.4.1", "b" * 40, "8")
    assert path.read_bytes() != first
