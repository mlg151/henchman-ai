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
from urllib.parse import urlparse

if TYPE_CHECKING:
    from collections.abc import Iterable


class SecurityError(Exception):
    """Base exception for security validation failures."""

    pass


class PathTraversalError(SecurityError):
    """Raised when a path traversal attempt is detected."""

    pass


class CommandInjectionError(SecurityError):
    """Raised when a command injection attempt is detected."""

    pass


class SSRFError(SecurityError):
    """Raised when an SSRF attempt is detected."""

    pass


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
        raise ValueError("Path cannot be empty")

    # Convert to Path object
    path_obj = Path(str(path)).expanduser().resolve()

    # Check for path traversal attempts
    if ".." in str(path):
        # Check if the resolved path actually escapes
        try:
            # Check if any parent component contains '..'
            for part in str(path).split(os.sep):
                if part == "..":
                    raise PathTraversalError(f"Path traversal detected: {path}")
        except Exception:
            raise PathTraversalError(f"Invalid path: {path}") from None

    # Restrict to base directory if specified
    if base_dir:
        base_path = Path(base_dir).expanduser().resolve()
        try:
            # Ensure the path is within base directory
            path_obj.relative_to(base_path)
        except ValueError:
            raise PathTraversalError(
                f"Path {path_obj} is outside allowed directory {base_path}"
            ) from None

    return path_obj


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
        raise ValueError("Command must be a non-empty string")

    # Strip leading/trailing whitespace
    command = command.strip()

    # Check for dangerous patterns
    dangerous_patterns = [
        r";\s*$",  # Command separator at end
        r"&\s*$",  # Background execution at end
        r"\|\s*$",  # Pipe at end
        r"`.*`",  # Command substitution
        r"\$\(.*\)",  # Command substitution
        r"\$\{.*\}",  # Variable expansion with command execution
        r">\s*/(?:dev|proc|sys|etc|bin|sbin|usr/bin|usr/sbin)\b",  # Redirect to system dirs
        r">>\s*/(?:dev|proc|sys|etc|bin|sbin|usr/bin|usr/sbin)\b",  # Append to system dirs
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, command):
            raise CommandInjectionError(f"Dangerous pattern detected: {pattern}")

    # Check for multiple commands
    if ";" in command or "&" in command or "|" in command:
        # Allow if it's part of a valid shell pipeline but validate each part
        parts = re.split(r"[;&|]", command)
        for part in parts:
            part = part.strip()
            if part:
                # Recursively validate each part
                sanitize_command(part, allowed_commands)

    # Validate against allowed commands if specified
    if allowed_commands and not any(command.startswith(cmd) for cmd in allowed_commands):
        raise CommandInjectionError(
            f"Command must start with one of: {', '.join(allowed_commands)}"
        )

    # Use shlex to safely split and rejoin (helps detect unclosed quotes)
    try:
        shlex.split(command)
    except ValueError as e:
        raise CommandInjectionError(f"Invalid shell syntax: {e}") from e

    return command


def validate_url(
    url: str,
    allowed_schemes: Iterable[str] = ("http", "https"),
    allowed_domains: Iterable[str] | None = None,
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
        raise ValueError("URL must be a non-empty string")

    try:
        parsed = urlparse(url)
    except Exception as e:
        raise SSRFError(f"Invalid URL: {e}") from e

    # Check scheme
    if not parsed.scheme:
        raise SSRFError("URL must have a scheme")
    if parsed.scheme not in allowed_schemes:
        raise SSRFError(f"Scheme {parsed.scheme} not allowed. Must be one of: {allowed_schemes}")

    # Check for basic SSRF patterns
    if block_localhost:
        localhost_patterns = [
            "localhost",
            "127.0.0.1",
            "::1",
            "0.0.0.0",
            "[::]",
        ]
        if parsed.hostname in localhost_patterns:
            raise SSRFError("Localhost URLs are not allowed")

    # Check for private IP addresses
    if block_private_ips and parsed.hostname:
        # Regex for private IP ranges
        private_ip_patterns = [
            r"^10\.",  # 10.0.0.0/8
            r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",  # 172.16.0.0/12
            r"^192\.168\.",  # 192.168.0.0/16
            r"^169\.254\.",  # Link-local
            r"^fc00:",  # IPv6 private
            r"^fd00:",  # IPv6 private
            r"^fe80:",  # IPv6 link-local
        ]

        for pattern in private_ip_patterns:
            if re.match(pattern, parsed.hostname):
                raise SSRFError(f"Private IP address not allowed: {parsed.hostname}")

    # Check domain whitelist if provided
    if allowed_domains and parsed.hostname and parsed.hostname not in allowed_domains:
        raise SSRFError(f"Domain {parsed.hostname} not in allowed list")

    # Check for suspicious URL patterns
    suspicious_patterns = [
        r"@.*@",  # Multiple @ symbols
        r"#.*#",  # Multiple # fragments
        r"\?.*\?",  # Multiple ? query strings
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, url):
            raise SSRFError(f"Suspicious URL pattern detected: {pattern}")

    return url


def sanitize_error_message(error: Exception | str) -> str:
    """Sanitize error messages to prevent information leakage.

    Args:
        error: The error exception or message.

    Returns:
        A sanitized error message safe for user display.
    """
    error_msg = str(error)

    # Remove system paths and sensitive information
    # Replace absolute paths with placeholders
    error_msg = re.sub(r"/[^\s]+", "[PATH]", error_msg)
    # Replace home directories
    error_msg = re.sub(r"~/[^\s]+", "[HOME_PATH]", error_msg)
    # Remove potential environment variable values
    error_msg = re.sub(r"=[^\s]+", "=[REDACTED]", error_msg)

    # Generic error messages for common exceptions
    if "Permission denied" in error_msg:
        return "Permission denied"
    elif "File not found" in error_msg or "No such file or directory" in error_msg:
        return "File not found"
    elif "Connection refused" in error_msg:
        return "Connection refused"
    elif "Timeout" in error_msg.lower():
        return "Operation timed out"

    # Return generic message for other errors
    return "An error occurred"


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

    Raises:
        OSError: If file operation fails.
    """
    path_obj = Path(path)
    temp_path = path_obj.with_suffix(f"{path_obj.suffix}.tmp")

    try:
        # Write to temporary file
        with open(temp_path, mode, encoding=encoding) as f:
            f.write(content)
        # Atomically rename to target
        temp_path.replace(path_obj)
    finally:
        # Clean up temp file if it still exists
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
    # Stat the file once and use that for operations
    stat_info = path_obj.stat()

    with open(path_obj, mode, encoding=encoding) as f:
        content: str = f.read()

    # Verify file hasn't been replaced (basic check)
    try:
        current_stat = path_obj.stat()
        if current_stat.st_ino != stat_info.st_ino or current_stat.st_size != stat_info.st_size:
            # File changed during read, but we already have the content
            # Log warning or handle as needed
            pass
    except OSError:
        # File disappeared after read
        pass

    return content
