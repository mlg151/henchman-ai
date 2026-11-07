"""Dedicated MCP auth storage is replaced privately without following symlinks."""

import os
import stat

import pytest

from henchman.mcp.auth import McpAuthService


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission-bit guarantee")
@pytest.mark.parametrize("existing", [False, True])
def test_auth_file_is_private_even_when_replacing_legacy_public_mode(tmp_path, existing):
    path = tmp_path / ".henchman" / "mcp" / "auth.json"
    if existing:
        path.parent.mkdir(parents=True)
        path.write_text('{"fixture": "old-canary"}')
        path.chmod(0o644)
    previous = os.umask(0o022)
    try:
        McpAuthService(tmp_path).set_token("fixture", "new-private-canary")
    finally:
        os.umask(previous)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert McpAuthService(tmp_path).get_token("fixture") == "new-private-canary"


def test_auth_store_rejects_symlink_without_modifying_referent(tmp_path):
    path = tmp_path / ".henchman" / "mcp" / "auth.json"
    path.parent.mkdir(parents=True)
    outside = tmp_path / "outside.json"
    outside.write_text('{"outside": "outside-canary"}')
    try:
        path.symlink_to(outside)
    except OSError as error:
        pytest.skip(f"Symlinks unavailable: {error}")
    with pytest.raises(OSError):
        McpAuthService(tmp_path).set_token("fixture", "private-canary")
    assert outside.read_text() == '{"outside": "outside-canary"}'


def test_failed_auth_replacement_preserves_previous_token_and_cleans_temporary(tmp_path, monkeypatch):
    service = McpAuthService(tmp_path)
    service.set_token("fixture", "old-canary")
    directory = tmp_path / ".henchman" / "mcp"

    def fail(*_args):
        raise PermissionError("injected replace failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(PermissionError):
        service.set_token("fixture", "new-private-canary")
    assert service.get_token("fixture") == "old-canary"
    assert {path.name for path in directory.iterdir()} == {"auth.json"}


def test_auth_read_checks_opened_descriptor_before_loading_json(tmp_path, monkeypatch):
    service = McpAuthService(tmp_path)
    service.set_token("fixture", "old-canary")
    reader, writer = os.pipe()
    os.close(writer)
    monkeypatch.setattr(os, "open", lambda *_args: reader)
    with pytest.raises(OSError, match="regular file"):
        service.get_token("fixture")
    with pytest.raises(OSError):
        os.fstat(reader)
