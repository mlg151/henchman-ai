"""Tests for Tier 7 integration blueprints."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.integrations.blueprints import export_blueprint, list_blueprints


def test_list_blueprints_covers_tier7_targets() -> None:
    """The blueprint registry should expose every Tier 7 export target."""

    blueprints = {blueprint.slug: blueprint for blueprint in list_blueprints()}

    assert set(blueprints) >= {
        "chrome-extension",
        "electron",
        "jetbrains",
        "react-native",
        "slack-app",
        "vscode",
    }
    assert blueprints["vscode"].surface == "ide"
    assert blueprints["jetbrains"].surface == "ide"
    assert blueprints["electron"].surface == "desktop"
    assert blueprints["react-native"].surface == "mobile"
    assert blueprints["chrome-extension"].surface == "chrome"
    assert blueprints["slack-app"].surface == "communication"


def test_export_blueprint_writes_expected_files(tmp_path: Path) -> None:
    """Exporting a blueprint should materialize its files into the destination."""

    written_files = export_blueprint("vscode", tmp_path)

    assert tmp_path / "package.json" in written_files
    assert tmp_path / "extension.js" in written_files
    assert '"name": "henchman-ai-vscode"' in (tmp_path / "package.json").read_text(
        encoding="utf-8",
    )
    assert "henchman.openChat" in (tmp_path / "extension.js").read_text(encoding="utf-8")


def test_export_blueprint_refuses_to_overwrite_existing_files(tmp_path: Path) -> None:
    """Blueprint exports should fail fast instead of clobbering existing files."""

    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    with pytest.raises(FileExistsError, match="package.json"):
        export_blueprint("vscode", tmp_path)
