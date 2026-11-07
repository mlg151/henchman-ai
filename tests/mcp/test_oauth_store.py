"""Persistent OAuth generations prevent stale login and refresh publication."""

import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress

import pytest

from henchman.mcp.auth import McpAuthService


def binding(client_id="public-client"):
    from henchman.mcp.oauth import OAuthBinding
    from tests.mcp.test_oauth_foundation import configuration

    return OAuthBinding.from_config("fixture", configuration(client_id=client_id))


def credentials(access="access-private-canary", refresh="refresh-private-canary", expiry=200):
    from henchman.mcp.oauth_store import OAuthCredentials

    return OAuthCredentials(access_token=access, refresh_token=refresh, token_endpoint="https://issuer.example/token",
                            scopes=("read",), issued_at=100, expires_at=expiry)


def store(tmp_path, **kwargs):
    from henchman.mcp.oauth_store import OAuthCredentialStore

    return OAuthCredentialStore(tmp_path, **kwargs)


def ready(service):
    authority = service.bind(binding())
    claim = service.begin_login(authority)
    return service.complete(claim, credentials())


def test_facade_and_read_only_status_do_not_promote_stdio_credentials(tmp_path):
    service = McpAuthService(tmp_path)
    service.set_token("fixture", "stdio-private-canary")
    oauth = service.oauth_store()
    assert oauth.status("fixture").state == "missing"
    assert not (tmp_path / ".henchman/mcp/oauth.json").exists()
    assert service.get_token("fixture") == "stdio-private-canary"


@pytest.mark.parametrize("transition", ["logout", "rebind"])
def test_late_login_cannot_restore_revoked_or_reconfigured_authority(tmp_path, transition):
    from henchman.mcp.oauth_store import OAuthStoreError

    first, second = store(tmp_path), store(tmp_path)
    claim = first.begin_login(first.bind(binding()))
    if transition == "logout":
        second.logout("fixture")
    else:
        second.bind(binding("other-client"))
    with pytest.raises(OAuthStoreError):
        first.complete(claim, credentials())
    persisted = json.loads((tmp_path / ".henchman/mcp/oauth.json").read_text())
    assert "access-private-canary" not in json.dumps(persisted)
    assert first.status("fixture").generation > claim.authority.generation


def test_refresh_claim_is_persisted_before_token_leaves_store_and_stays_unavailable(tmp_path):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path, clock=lambda: 150)
    authority = ready(service)
    refresh = service.begin_refresh(authority)
    assert refresh.refresh_token == "refresh-private-canary"
    assert refresh.token_endpoint == "https://issuer.example/token"
    assert "private-canary" not in repr(refresh)
    reopened = store(tmp_path, clock=lambda: 150)
    assert reopened.status("fixture").state == "refresh_started"
    assert reopened.credentials(refresh.authority) is None
    assert "refresh-private-canary" not in (tmp_path / ".henchman/mcp/oauth.json").read_text()
    with pytest.raises(OAuthStoreError):
        reopened.begin_refresh(refresh.authority)
    with pytest.raises(OAuthStoreError):
        reopened.begin_login(refresh.authority)
    reopened.logout("fixture")
    with pytest.raises(OAuthStoreError):
        service.complete(refresh, credentials("late-access", "late-refresh"))


def test_refresh_success_and_abandonment_are_one_time_generation_changes(tmp_path):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path, clock=lambda: 150)
    authority = ready(service)
    claim = service.begin_refresh(authority)
    current = service.complete(claim, credentials("next-access", "next-refresh"))
    assert service.credentials(current).access_token == "next-access"
    with pytest.raises(OAuthStoreError):
        service.complete(claim, credentials())
    next_claim = service.begin_refresh(current)
    service.abandon(next_claim)
    assert service.status("fixture").state == "needs_login"
    assert service.credentials(service.bind(binding())) is None


def test_two_handles_cannot_claim_same_rotating_refresh_token(tmp_path):
    from henchman.mcp.oauth_store import OAuthStoreError

    authority = ready(store(tmp_path))

    def attempt(_):
        try:
            return store(tmp_path).begin_refresh(authority)
        except OAuthStoreError:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(attempt, range(2)))
    assert sum(claim is not None for claim in claims) == 1


def test_unknown_zero_and_expired_credentials_remain_distinct(tmp_path):
    for expiry, clock, available in ((None, 150, True), (100, 100, False), (200, 201, False), (200, 90, False)):
        service = store(tmp_path, clock=lambda clock=clock: clock)
        service.logout("fixture")
        authority = service.complete(service.begin_login(service.bind(binding())), credentials(expiry=expiry))
        assert service.status("fixture").expires_at == expiry
        assert (service.credentials(authority) is not None) is available


def test_auth_store_failure_retains_original_and_does_not_release_refresh(tmp_path, monkeypatch):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path)
    authority = ready(service)
    path = tmp_path / ".henchman/mcp/oauth.json"
    original = path.read_bytes()

    def fail(*_args, **_kwargs):
        raise OSError("private-storage-canary")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OAuthStoreError) as caught:
        service.begin_refresh(authority)
    assert "private-storage-canary" not in str(caught.value)
    assert path.read_bytes() == original
    assert not list(path.parent.glob(".oauth-*.tmp"))


def test_corrupt_store_is_preserved_with_value_free_diagnostic(tmp_path):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path)
    ready(service)
    path = tmp_path / ".henchman/mcp/oauth.json"
    path.write_text('{"private-corruption-canary":')
    original = path.read_bytes()
    with pytest.raises(OAuthStoreError) as caught:
        service.logout("fixture")
    assert "private-corruption-canary" not in str(caught.value)
    assert path.read_bytes() == original


@pytest.mark.parametrize("target", ["oauth.json", "oauth.lock", "directory"])
def test_store_refuses_symlinks_without_touching_referent(tmp_path, target):
    from henchman.mcp.oauth_store import OAuthStoreError

    root = tmp_path / "project"
    root.mkdir()
    directory = root / ".henchman/mcp"
    directory.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("unchanged")
    try:
        if target == "directory":
            directory.rmdir()
            directory.symlink_to(outside, target_is_directory=True)
        else:
            (directory / target).symlink_to(sentinel)
    except OSError:
        pytest.skip("Symlinks unavailable")
    with pytest.raises(OAuthStoreError):
        store(root).bind(binding())
    assert sentinel.read_text() == "unchanged"
    assert list(outside.iterdir()) == [sentinel]


@pytest.mark.skipif(os.name != "posix", reason="POSIX mode guarantee")
def test_credentials_are_private_and_use_canonical_write_path(tmp_path):
    legacy = tmp_path / ".hENCHMAN"
    canonical = tmp_path / ".henchman"
    legacy.mkdir()
    service = store(tmp_path)
    path = tmp_path / ".henchman/mcp/oauth.json"
    assert service._path == path
    ready(service)
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    # Case-insensitive filesystems alias these spellings. The write path must
    # still be canonical; distinct legacy directories must remain untouched.
    if not legacy.samefile(canonical):
        assert list(legacy.iterdir()) == []


@pytest.mark.parametrize("corruption", ["version_bool", "oversized", "project", "ready_without_token"])
def test_strict_storage_corruption_is_not_treated_as_empty(tmp_path, corruption):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path)
    ready(service)
    path = tmp_path / ".henchman/mcp/oauth.json"
    data = json.loads(path.read_text())
    if corruption == "version_bool":
        data["version"] = True
    elif corruption == "oversized":
        data["ignored"] = "x" * (1024 * 1024)
    elif corruption == "project":
        data["project_hash"] = "0" * 64
    else:
        data["records"]["fixture"]["credentials"] = None
    path.write_text(json.dumps(data))
    original = path.read_bytes()
    with pytest.raises(OAuthStoreError):
        service.logout("fixture")
    assert path.read_bytes() == original


def test_missing_storage_cannot_recreate_old_claim_authority(tmp_path):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path)
    claim = service.begin_login(service.bind(binding()))
    (tmp_path / ".henchman/mcp/oauth.json").unlink()
    service.bind(binding())
    with pytest.raises(OAuthStoreError):
        service.complete(claim, credentials())


def test_lost_commit_acknowledgement_does_not_allow_duplicate_completion(tmp_path, monkeypatch):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path, clock=lambda: 150)
    claim = service.begin_login(service.bind(binding()))
    original = os.replace

    def committed_then_failed(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("private-ack-canary")

    monkeypatch.setattr(os, "replace", committed_then_failed)
    with pytest.raises(OAuthStoreError):
        service.complete(claim, credentials())
    monkeypatch.setattr(os, "replace", original)
    assert service.status("fixture").state == "ready"
    with pytest.raises(OAuthStoreError):
        service.complete(claim, credentials())


def test_store_cannot_publish_unreadable_deep_or_excessive_payload(tmp_path):
    from henchman.config.schema import McpServerConfig
    from henchman.mcp.oauth import OAuthBinding
    from henchman.mcp.oauth_store import OAuthCredentials, OAuthStoreError

    service = store(tmp_path)
    bounded_failure = False
    for index in range(100):
        identity = OAuthBinding.from_config(str(index), McpServerConfig(transport="streamable_http", url="https://resource.example/mcp",
                                               oauth={"issuer": "https://issuer.example", "client_id": "public"}))
        token = OAuthCredentials(access_token="a", token_endpoint="https://issuer.example/token",
                                 scopes=tuple(f"scope{x}" for x in range(128)), issued_at=100)
        try:
            service.complete(service.begin_login(service.bind(identity)), token)
        except OAuthStoreError:
            bounded_failure = True
            break
    assert bounded_failure
    assert service.status("0").state == "ready"


def test_pending_claim_guard_rechecks_logout_before_future_token_dispatch(tmp_path):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path)
    claim = service.begin_refresh(ready(service))
    service.check_claim(claim)
    store(tmp_path).logout("fixture")
    with pytest.raises(OAuthStoreError):
        service.check_claim(claim)


def test_short_write_never_publishes_new_credentials(tmp_path, monkeypatch):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path)
    authority = ready(service)
    path = tmp_path / ".henchman/mcp/oauth.json"
    original = path.read_bytes()
    original_fdopen = os.fdopen

    class ShortWriter:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.handle.__exit__(*args)

        def write(self, raw):
            return self.handle.write(raw[:1])

    def open_short(descriptor, mode, **kwargs):
        handle = original_fdopen(descriptor, mode, **kwargs)
        return ShortWriter(handle) if mode == "wb" else handle

    monkeypatch.setattr(os, "fdopen", open_short)
    with pytest.raises(OAuthStoreError):
        service.begin_refresh(authority)
    assert path.read_bytes() == original
    assert not list(path.parent.glob(".oauth-*.tmp"))


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor-relative protection")
def test_directory_replacement_cannot_redirect_storage_io(tmp_path, monkeypatch):
    from pathlib import Path

    from henchman.mcp.oauth_store import OAuthStoreError

    directory = tmp_path / ".henchman/mcp"
    directory.mkdir(parents=True)
    parked, outside = tmp_path / "parked", tmp_path / "outside"
    outside.mkdir()
    original = os.open
    moved = False

    def open_after_swap(path, *args, **kwargs):
        nonlocal moved
        if Path(path).name == "oauth.lock" and not moved:
            moved = True
            directory.rename(parked)
            directory.symlink_to(outside, target_is_directory=True)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", open_after_swap)
    with suppress(OAuthStoreError):
        store(tmp_path).bind(binding())
    assert moved
    assert list(outside.iterdir()) == []


@pytest.mark.parametrize("operation", ["read", "refresh"])
def test_edited_persisted_token_endpoint_is_rechecked_before_release_or_claim(tmp_path, operation):
    from henchman.mcp.oauth_store import OAuthStoreError

    service = store(tmp_path, clock=lambda: 150)
    authority = ready(service)
    path = tmp_path / ".henchman/mcp/oauth.json"
    payload = json.loads(path.read_text())
    payload["records"]["fixture"]["credentials"]["token_endpoint"] = "https://unapproved.example/private-canary"
    path.write_text(json.dumps(payload))
    original = path.read_bytes()
    with pytest.raises(OAuthStoreError) as caught:
        if operation == "read":
            service.credentials(authority)
        else:
            service.begin_refresh(authority)
    assert "private-canary" not in str(caught.value)
    assert path.read_bytes() == original
    assert service.status("fixture").state == "ready"
