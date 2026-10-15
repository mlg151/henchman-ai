"""Security utilities for Henchman tools.

This module provides security validation and sanitization functions
to protect against common vulnerabilities in tool implementations.
"""

from __future__ import annotations

import os
import re
import shlex
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import ParseResult, urlparse

if TYPE_CHECKING:
    from collections.abc import Iterable

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
_DANGEROUS_COMMAND_PATTERNS: list[str] = [
    r"\\n",  # Embedded newline
    r"`.*`",  # Command substitution
    r"\$\(.*\)",  # Command substitution
    r"\$\{[^}]*@[A-Z]}",  # Parameter transformation (e.g. @P)
    r"\$\{![^}]*}",  # Indirect expansion (!var)
    r"\$\{.*\}",  # Variable expansion with command execution
    r"\|$",  # Trailing pipe (pipe without following command)
]

_LOCALHOST_PATTERNS: frozenset[str] = frozenset(
    ["localhost", "127.0.0.1", "::1", "0.0.0.0", "[::]"],
)

_PRIVATE_IP_PATTERNS: list[str] = [
    r"^10\.",  # 10.0.0.0/8
    r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",  # 172.16.0.0/12
    r"^192\.168\.",  # 192.168.0.0/16
    r"^169\.254\.",  # Link-local
    r"^fc00:",  # IPv6 private
    r"^fd00:",  # IPv6 private
    r"^fe80:",  # IPv6 link-local
]

_SUSPICIOUS_URL_PATTERNS: list[str] = [
    r"@.*@",  # Multiple @ symbols
    r"#.*#",  # Multiple # fragments
    r"\?.*\?",  # Multiple ? query strings
]

# Ampersands belonging to redirects (>&, <&, &>, &>>) are not separators.
_COMMAND_SEPARATOR_PATTERN = re.compile(r"[;|]|(?<![<>])&(?!>)")

_TIMEOUT_KEYWORDS: tuple[str, ...] = ("timeout", "timed out")
_NETWORK_KEYWORDS: tuple[str, ...] = ("network", "connection")

_PATH_PATTERN: re.Pattern[str] = re.compile(r"/[^\s]+")
_HOME_PATH_PATTERN: re.Pattern[str] = re.compile(r"~/[^\s]+")
_ENV_VAR_PATTERN: re.Pattern[str] = re.compile(r"=[^\s]+")

# Map from pattern to human-readable description for error messages.
# Order matters: more specific patterns must come before general ones.
_DANGEROUS_PATTERN_DESCRIPTIONS: dict[str, str] = {
    r"\\n": "embedded newline",
    r"`.*`": "command substitution",
    r"\$\(.*\)": "command substitution",
    r"\$\{[^}]*@[A-Z]}": "parameter transformation (@P)",
    r"\$\{![^}]*}": "indirect expansion (!var)",
    r"\$\{.*\}": "variable expansion",
    r"\|$": "trailing pipe",
}


def _find_first_matching_pattern(text: str, patterns: list[str]) -> str | None:
    """Return the first pattern from patterns that matches text, or None."""
    return next((p for p in patterns if re.search(p, text)), None)


def _message_matches_any_keyword(msg: str, keywords: tuple[str, ...]) -> bool:
    """Return True if any keyword appears in the lower-cased msg."""
    lower = msg.lower()
    return any(kw in lower for kw in keywords)


# ---------------------------------------------------------------------------
# Exception classes
# ---------------------------------------------------------------------------
class SecurityError(Exception):
    """Base exception for security validation failures."""


class PathTraversalError(SecurityError):
    """Raised when a path traversal attempt is detected."""


class CommandInjectionError(SecurityError):
    """Raised when a command injection attempt is detected."""


class SSRFError(SecurityError):
    """Raised when an SSRF attempt is detected."""


# ---------------------------------------------------------------------------
# Path validation helpers
# ---------------------------------------------------------------------------
def _check_path_traversal(path: str | Path) -> None:
    """Raise PathTraversalError if path contains traversal sequences."""
    path_str = str(path)
    if ".." not in path_str:
        return
    for part in Path(path_str).parts:
        if part == "..":
            msg = f"Path traversal detected: {path}"
            raise PathTraversalError(msg)


def _check_within_base_dir(path_obj: Path, base_path: Path) -> None:
    """Raise PathTraversalError if path_obj is not within base_path."""
    try:
        path_obj.relative_to(base_path)
    except ValueError:
        msg = f"Path {path_obj} is outside allowed directory {base_path}"
        raise PathTraversalError(msg) from None


def validate_path(path: str | Path, base_dir: str | Path | None = None) -> Path:
    """Validate and normalize a file path, preventing path traversal.

    Args:
        path: The path to validate.
        base_dir: Optional base directory to restrict paths to.
                  If provided, the resolved path must be within this directory.

    Returns:
        The normalized, absolute Path object.

    Raises:
        PathTraversalError: If path traversal is detected or path is outside base_dir.
        ValueError: If path is empty or invalid.
    """
    if not path:
        msg = "Path cannot be empty"
        raise ValueError(msg)

    path_obj = Path(str(path)).expanduser().resolve()
    _check_path_traversal(path)

    if base_dir:
        base_path = Path(base_dir).expanduser().resolve()
        _check_within_base_dir(path_obj, base_path)

    return path_obj


# ---------------------------------------------------------------------------
# Command sanitization helpers
# ---------------------------------------------------------------------------
def _check_for_dangerous_patterns(command: str) -> None:
    """Raise CommandInjectionError if command matches any dangerous pattern."""
    for pattern in _DANGEROUS_COMMAND_PATTERNS:
        if re.search(pattern, command):
            description = _DANGEROUS_PATTERN_DESCRIPTIONS.get(pattern, pattern)
            msg = f"Dangerous pattern detected: {description}"
            raise CommandInjectionError(msg)


def _validate_sub_commands(command: str, allowed_commands: Iterable[str] | None) -> None:
    """Recursively validate each sub-command split by ; & | operators."""
    for raw_part in _COMMAND_SEPARATOR_PATTERN.split(command):
        stripped = raw_part.strip()
        if stripped:
            sanitize_command(stripped, allowed_commands)


def sanitize_command(command: str, allowed_commands: Iterable[str] | None = None) -> str:
    """Sanitize a shell command to prevent command injection.

    Args:
        command: The command string to sanitize.
        allowed_commands: Optional list of allowed command prefixes.
                         If provided, command must start with one of these.

    Returns:
        The sanitized command string.

    Raises:
        CommandInjectionError: If command injection is detected.
        ValueError: If command is empty or invalid.
    """
    if not command or not isinstance(command, str):
        msg = "Command must be a non-empty string"
        raise ValueError(msg)

    command = command.strip()

    # Check for control characters (newlines, tabs, null bytes, etc.)
    for i, char in enumerate(command):
        if 0 < ord(char) < 32 or ord(char) == 127:
            msg = f"control characters detected at position {i}"
            raise CommandInjectionError(msg)

    _check_for_dangerous_patterns(command)

    # Subcommands only need a separate pass for an explicit prefix policy.
    # Whole-command checks cover the default path; splitting there would break
    # quoted payloads such as python -c "x = 1; print(x)" before execution.
    if allowed_commands and _COMMAND_SEPARATOR_PATTERN.search(command):
        _validate_sub_commands(command, allowed_commands)

    if allowed_commands and not any(command.startswith(cmd) for cmd in allowed_commands):
        allowed_list = ", ".join(allowed_commands)
        msg = f"Command must start with one of: {allowed_list}"
        raise CommandInjectionError(msg)

    try:
        shlex.split(command)
    except ValueError as e:
        msg = f"Invalid shell syntax: {e}"
        raise CommandInjectionError(msg) from e

    return command


# ---------------------------------------------------------------------------
# URL validation helpers
# ---------------------------------------------------------------------------
def _check_url_scheme(parsed: ParseResult, allowed_schemes: Iterable[str]) -> None:
    """Raise SSRFError if URL scheme is missing or not in allowed_schemes."""
    if not parsed.scheme:
        msg = "URL must have a scheme"
        raise SSRFError(msg)
    if parsed.scheme not in allowed_schemes:
        msg = f"Scheme {parsed.scheme} not allowed. Must be one of: {allowed_schemes}"
        raise SSRFError(msg)


def _check_localhost_url(parsed: ParseResult) -> None:
    """Raise SSRFError if URL points to a localhost address."""
    if parsed.hostname in _LOCALHOST_PATTERNS:
        msg = "Localhost URLs are not allowed"
        raise SSRFError(msg)


def _check_private_ip_address(parsed: ParseResult) -> None:
    """Raise SSRFError if URL points to a private IP address."""
    hostname = parsed.hostname
    if not hostname:
        return
    for pattern in _PRIVATE_IP_PATTERNS:
        if re.match(pattern, hostname):
            msg = f"Private IP address not allowed: {hostname}"
            raise SSRFError(msg)


def _check_domain_whitelist(
    parsed: ParseResult,
    allowed_domains: Iterable[str] | None,
) -> None:
    """Raise SSRFError if URL domain is not in the allowed list."""
    hostname = parsed.hostname
    if allowed_domains and hostname and hostname not in allowed_domains:
        msg = f"Domain {hostname} not in allowed list"
        raise SSRFError(msg)


def _check_suspicious_url_patterns(url: str) -> None:
    """Raise SSRFError if URL matches suspicious patterns."""
    if pattern := _find_first_matching_pattern(url, _SUSPICIOUS_URL_PATTERNS):
        msg = f"Suspicious URL pattern detected: {pattern}"
        raise SSRFError(msg)


def validate_url(
    url: str,
    allowed_schemes: Iterable[str] = ("http", "https"),
    allowed_domains: Iterable[str] | None = None,
    *,
    block_private_ips: bool = True,
    block_localhost: bool = True,
) -> str:
    """Validate a URL to prevent SSRF attacks.

    Args:
        url: The URL to validate.
        allowed_schemes: Allowed URL schemes (default: http, https).
        allowed_domains: Optional list of allowed domains.
                         If provided, URL domain must be in this list.
        block_private_ips: Whether to block private IP addresses (default: True).
        block_localhost: Whether to block localhost/127.0.0.1 (default: True).

    Returns:
        The validated URL.

    Raises:
        SSRFError: If SSRF attempt is detected.
        ValueError: If URL is empty or invalid.
    """
    if not url or not isinstance(url, str):
        msg = "URL must be a non-empty string"
        raise ValueError(msg)

    try:
        parsed = urlparse(url)
    except Exception as e:
        msg = f"Invalid URL: {e}"
        raise SSRFError(msg) from e

    _check_url_scheme(parsed, allowed_schemes)

    if block_localhost:
        _check_localhost_url(parsed)

    if block_private_ips:
        _check_private_ip_address(parsed)

    _check_domain_whitelist(parsed, allowed_domains)
    _check_suspicious_url_patterns(url)

    return url


# ---------------------------------------------------------------------------
# Error message sanitization helpers
# ---------------------------------------------------------------------------
def sanitize_error_message(error: Exception | str) -> str:
    """Sanitize error messages to prevent information leakage.

    Args:
        error: The error exception or message.

    Returns:
        A sanitized error message safe for user display.
    """
    error_msg = str(error)

    # Normalize control characters to spaces
    error_msg = re.sub(r"[\x00-\x1f\x7f]", " ", error_msg)
    error_msg = re.sub(r"  +", " ", error_msg)

    error_msg = _HOME_PATH_PATTERN.sub("[HOME_PATH]", error_msg)
    error_msg = _PATH_PATTERN.sub("[PATH]", error_msg)
    error_msg = _ENV_VAR_PATTERN.sub("=[REDACTED]", error_msg)

    if "Permission denied" in error_msg:
        return "Permission denied"
    if "File not found" in error_msg or "No such file or directory" in error_msg:
        return "File not found"
    if "Connection refused" in error_msg:
        return "Connection refused"
    if _message_matches_any_keyword(error_msg, _TIMEOUT_KEYWORDS):
        return _PATH_PATTERN.sub("[PATH]", error_msg)
    if _message_matches_any_keyword(error_msg, _NETWORK_KEYWORDS):
        return _PATH_PATTERN.sub("[PATH]", error_msg)

    return error_msg


# ---------------------------------------------------------------------------
# Atomic file I/O
# ---------------------------------------------------------------------------
def atomic_write(
    path: str | Path,
    content: str,
    mode: str = "w",
    encoding: str = "utf-8",
) -> None:
    """Write content to a file atomically to prevent TOCTOU race conditions.

    Args:
        path: Path to write to.
        content: Content to write.
        mode: File mode (default: 'w').
        encoding: File encoding (default: 'utf-8').

    Returns:
        None

    Raises:
        OSError: If file operation fails.
    """
    path_obj = Path(path)

    # Check write permissions on existing file before attempting write
    if path_obj.exists() and not os.access(str(path_obj), os.W_OK):
        msg = f"Permission denied: {path_obj}"
        raise PermissionError(msg)

    temp_path = path_obj.with_suffix(f"{path_obj.suffix}.tmp")

    try:
        with temp_path.open(mode, encoding=encoding) as f:
            f.write(content)
        temp_path.replace(path_obj)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def atomic_read(path: str | Path, mode: str = "r", encoding: str = "utf-8") -> str:
    """Read a file with basic TOCTOU protection.

    Note: This doesn't fully prevent TOCTOU but reduces the window.

    Args:
        path: Path to read from.
        mode: File mode (default: 'r').
        encoding: File encoding (default: 'utf-8').

    Returns:
        File contents.

    Raises:
        OSError: If file operation fails.
    """
    path_obj = Path(path)
    stat_info = path_obj.stat()

    with path_obj.open(mode, encoding=encoding) as f:
        content: str = f.read()

    try:
        current_stat = path_obj.stat()
        if current_stat.st_ino != stat_info.st_ino or current_stat.st_size != stat_info.st_size:
            pass
    except OSError:
        pass

    return content
