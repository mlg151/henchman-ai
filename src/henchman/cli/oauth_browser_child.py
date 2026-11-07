"""Isolated, standard-library-only desktop launcher with a bounded stdin protocol."""

from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Mapping
from typing import BinaryIO
from urllib.parse import urlsplit

MAX_URL_BYTES = 8192
_ENVIRONMENT = frozenset({
    "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "SYSTEMROOT", "WINDIR", "APPDATA", "LOCALAPPDATA",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY",
    "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION",
    "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CONFIG_DIRS", "XDG_DATA_DIRS", "DBUS_SESSION_BUS_ADDRESS",
    "XDG_ACTIVATION_TOKEN", "DESKTOP_STARTUP_ID", "KDE_FULL_SESSION", "KDE_SESSION_VERSION",
})


def browser_environment(source: Mapping[str, str]) -> dict[str, str]:
    """Retain required OS/desktop state without provider keys or command templates."""
    result = {key: value for key, value in source.items() if key.upper() in _ENVIRONMENT}
    path = next((value for key, value in source.items() if key.upper() == "PATH"), os.defpath)
    entries = [entry for entry in path.split(os.pathsep) if entry and os.path.isabs(entry)]
    if not entries:
        entries = [entry for entry in os.defpath.split(os.pathsep) if entry and os.path.isabs(entry)]
    result["PATH"] = os.pathsep.join(entries)
    return result


def valid_authorization_url(value: str) -> bool:
    """Accept a bounded HTTPS URL only; never interpret a path or command."""
    try:
        if (not isinstance(value, str) or not value or "#" in value or "\\" in value
            or len(value.encode("utf-8")) > MAX_URL_BYTES
            or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)):
            return False
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None
                and parsed.password is None and not parsed.fragment and (parsed.port is None or 1 <= parsed.port <= 65535))
    except (ValueError, UnicodeError):
        return False


def resolve_backend(platform: str, environment: Mapping[str, str]) -> tuple[str, ...] | None:
    """Resolve one desktop adapter, without consulting BROWSER command templates."""
    if platform == "win32":
        return ("win32",) if callable(getattr(os, "startfile", None)) else None
    if platform == "darwin":
        path = "/usr/bin/open"
    elif platform.startswith("linux"):
        if not environment.get("DISPLAY") and not environment.get("WAYLAND_DISPLAY"):
            return None
        search_path = environment.get("PATH", "")
        if not search_path:
            return None
        path = shutil.which("xdg-open", path=search_path) or ""
    else:
        return None
    if not path or not os.path.isabs(path) or not os.path.isfile(path) or not os.access(path, os.X_OK):
        return None
    return (path,)


def redirect_protocol() -> None:
    """No desktop process inherits the authorization input or control-output pipe."""
    descriptor = os.open(os.devnull, os.O_RDWR)
    try:
        for target in (0, 1, 2):
            os.dup2(descriptor, target)
    finally:
        if descriptor > 2:
            os.close(descriptor)


def launch(backend: tuple[str, ...], url: str, environment: Mapping[str, str]) -> None:
    """Replace the Unix launcher PID, or call the native Windows URL handler."""
    if backend == ("win32",):
        os.startfile(url, "open")  # type: ignore[attr-defined]  # Windows-only stdlib adapter.
    else:
        os.execve(backend[0], [*backend, url], dict(environment))


def run_protocol(source: BinaryIO, output: BinaryIO, environment: Mapping[str, str]) -> int:
    """Emit fixed control words only; all rejected URL and OS details stay private."""
    try:
        backend = resolve_backend(sys.platform, environment)
        if backend is None:
            output.write(b"UNAVAILABLE\n")
            output.flush()
            return 2
        output.write(b"READY\n")
        output.flush()
        raw = source.readline(MAX_URL_BYTES + 2)
        if not raw.endswith(b"\n") or len(raw) > MAX_URL_BYTES + 1 or source.read(1):
            raise ValueError
        url = raw[:-1].decode("utf-8")
        if not valid_authorization_url(url):
            raise ValueError
        redirect_protocol()
        launch(backend, url, environment)
        return 0
    except BaseException:
        try:
            output.write(b"FAILED\n")
            output.flush()
        except (OSError, ValueError):
            pass
        return 1


def main() -> int:
    if len(sys.argv) != 1:
        return 1
    environment = browser_environment(os.environ)
    os.environ.clear()
    os.environ.update(environment)
    return run_protocol(sys.stdin.buffer, sys.stdout.buffer, environment)


if __name__ == "__main__":
    raise SystemExit(main())
