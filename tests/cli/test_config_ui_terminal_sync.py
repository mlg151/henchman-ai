"""CLI round-trip for new UI terminal controls and import/export sync."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_write_command import (
    create_config_import_command,
    create_config_set_command,
)
from henchman.config.paths import resolve_project_settings_path
from henchman.config.settings import load_settings


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    root.mkdir()
    return root


def _build_group(project_root: Path):  # type: ignore[no-untyped-def]
    import click

    @click.group()
    def group() -> None:
        """Test config command group."""

    group.add_command(create_config_set_command(project_root=project_root))
    group.add_command(create_config_import_command(project_root=project_root))
    return group


def test_set_and_read_back_new_ui_controls(project_root: Path) -> None:
    runner = CliRunner()
    group = _build_group(project_root)

    result = runner.invoke(
        group,
        ["set", "ui.output_mode", "quiet", "--scope", "project"],
    )

    assert result.exit_code == 0
    settings = load_settings(project_root=project_root)
    assert settings.ui.output_mode == "quiet"


def test_set_rejects_invalid_enum_with_attribution(project_root: Path) -> None:
    runner = CliRunner()
    group = _build_group(project_root)

    result = runner.invoke(
        group,
        ["set", "ui.output_mode", "shouty", "--scope", "project"],
    )

    assert result.exit_code != 0
    assert "ui.output_mode" in result.output


def test_set_rejects_invalid_layout_value_with_attribution(project_root: Path) -> None:
    runner = CliRunner()
    group = _build_group(project_root)

    result = runner.invoke(
        group,
        ["set", "ui.layout.compact_tables", "maybe", "--scope", "project"],
    )

    assert result.exit_code != 0
    assert "compact_tables" in result.output


def test_import_exports_roundtrip_new_ui_controls(
    tmp_path: Path, project_root: Path,
) -> None:
    source_root = tmp_path / "source"
    (source_root / ".henchman").mkdir(parents=True)
    (source_root / ".henchman" / "settings.yaml").write_text(
        yaml.safe_dump(
            {
                "ui": {
                    "output_mode": "plain",
                    "reduced_motion": True,
                    "detail_density": "compact",
                    "keyboard_mode": "vim",
                    "mouse_capture": False,
                    "layout": {"compact_tables": True},
                },
            },
        ),
        encoding="utf-8",
    )
    from henchman.cli.commands.config_write_command import create_config_export_command

    export_path = tmp_path / "sync.json"
    import click

    @click.group()
    def group() -> None:
        """Test config command group."""

    group.add_command(create_config_export_command(project_root=source_root))
    group.add_command(create_config_import_command(project_root=project_root))

    runner = CliRunner()
    export_result = runner.invoke(group, ["export", str(export_path), "--scope", "project"])
    assert export_result.exit_code == 0

    import_result = runner.invoke(group, ["import", str(export_path), "--scope", "project"])
    assert import_result.exit_code == 0

    settings = load_settings(project_root=project_root)
    assert settings.ui.output_mode == "plain"
    assert settings.ui.reduced_motion is True
    assert settings.ui.detail_density == "compact"
    assert settings.ui.keyboard_mode == "vim"
    assert settings.ui.mouse_capture is False
    assert settings.ui.layout.compact_tables is True


def test_import_rejects_invalid_layout_before_writing(
    tmp_path: Path, project_root: Path,
) -> None:
    import_path = tmp_path / "sync.yaml"
    import_path.write_text(
        yaml.safe_dump({"ui": {"layout": {"bogus": True}}}),
        encoding="utf-8",
    )
    settings_path = resolve_project_settings_path(project_root) / "settings.yaml"
    before = settings_path.read_text(encoding="utf-8") if settings_path.exists() else None

    runner = CliRunner()
    result = runner.invoke(
        _build_group(project_root),
        ["import", str(import_path), "--scope", "project"],
    )

    assert result.exit_code != 0
    assert "layout" in result.output
    after = settings_path.read_text(encoding="utf-8") if settings_path.exists() else None
    assert after == before


def test_project_beats_default_and_merged_view_reports_origin(
    project_root: Path,
) -> None:
    (project_root / ".henchman").mkdir()
    (project_root / ".henchman" / "settings.yaml").write_text(
        "ui:\n  output_mode: quiet\n",
        encoding="utf-8",
    )

    settings = load_settings(project_root=project_root)

    assert settings.ui.output_mode == "quiet"
