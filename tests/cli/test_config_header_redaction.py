"""Config display redacts credential headers and preserves ordinary headers."""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from henchman.cli.commands.config_command import create_config_command


@pytest.mark.parametrize("group", [True, False])
@pytest.mark.parametrize(
    ("header", "sensitive"),
    [
        ("Authorization", True),
        ("Proxy-Authorization", True),
        ("Cookie", True),
        ("Set-Cookie", True),
        ("User-Agent", False),
    ],
)
def test_config_header_redaction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    header: str,
    sensitive: bool,
    group: bool,
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    for name in ("HENCHMAN_SETTINGS_PATH", "HENCHMAN_PROVIDER", "HENCHMAN_MODEL"):
        monkeypatch.delenv(name, raising=False)
    project_root = tmp_path / "project"
    settings_dir = project_root / ".henchman"
    settings_dir.mkdir(parents=True)
    settings = {
        "providers": {
            "openai_compat": {"extra_headers": {header: "dummy-review-value"}}
        }
    }
    (settings_dir / "settings.yaml").write_text(
        yaml.safe_dump(settings), encoding="utf-8"
    )
    key = (
        "providers.openai_compat"
        if group
        else f"providers.openai_compat.extra_headers.{header}"
    )
    result = CliRunner().invoke(create_config_command(project_root=project_root), ["get", key])
    assert result.exit_code == 0, (result.output, result.exception)
    payload = yaml.safe_load(result.output)
    value = payload["value"]["extra_headers"][header] if group else payload["value"]
    if sensitive:
        assert value == "<redacted>"
        assert "dummy-review-value" not in result.output
    else:
        assert value == "dummy-review-value"
        assert "dummy-review-value" in result.output
