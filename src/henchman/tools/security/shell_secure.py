"""Secure shell tool implementation with command injection protection.

This module provides a secure wrapper around the shell tool that validates
and sanitizes commands to prevent command injection attacks.
"""

from __future__ import annotations

import copy
import os
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.shell import ShellTool

# ---------------------------------------------------------------------------
# Module-level constants (magic number extractions)
# ---------------------------------------------------------------------------
_DEFAULT_MAX_COMMAND_LENGTH: int = 4096
_DEFAULT_MAX_ARGS: int = 50
_STRICT_MAX_COMMAND_LENGTH: int = 1024
_STRICT_MAX_ARGS: int = 20
_MODERATE_MAX_COMMAND_LENGTH: int = 2048
_MODERATE_MAX_ARGS: int = 30
_PERMISSIVE_MAX_COMMAND_LENGTH: int = 8192
_PERMISSIVE_MAX_ARGS: int = 100

# ---------------------------------------------------------------------------
# Default configuration builders (extracted from __post_init__)
# ---------------------------------------------------------------------------


def _default_allowed_commands() -> set[str]:
    """Return the default set of allowed commands."""
    return {
        "echo",
        "ls",
        "cat",
        "grep",
        "find",
        "pwd",
        "cd",
        "mkdir",
        "rmdir",
        "cp",
        "mv",
        "rm",
        "touch",
        "chmod",
        "chown",
        "stat",
        "file",
        "head",
        "tail",
        "wc",
        "sort",
        "uniq",
        "cut",
        "paste",
        "tr",
        "sed",
        "awk",
        "python",
        "python3",
        "pip",
        "pip3",
        "git",
        "curl",
        "wget",
        "tar",
        "gzip",
        "gunzip",
        "zip",
        "unzip",
        "df",
        "du",
        "ps",
        "top",
        "kill",
        "killall",
        "pgrep",
        "pkill",
        "date",
        "time",
        "which",
        "whereis",
        "locate",
        "updatedb",
    }


def _default_denied_patterns() -> list[str]:
    """Return the default list of denied command patterns."""
    return [
        r"\|\s*sh\s*$",  # Piping to shell
        r"\|\s*bash\s*$",
        r"\|\s*zsh\s*$",
        r"\|\s*ksh\s*$",
        r";\s*sh\s*$",  # Command separator then shell
        r";\s*bash\s*$",
        r";\s*zsh\s*$",
        r";\s*ksh\s*$",
        r"`.*`",  # Backticks for command substitution
        r"\$\(.*\)",  # $(...) command substitution
        r"\brm\s+-(rf|fr)\b",  # Dangerous rm flags
        r"\bdd\s+.*(if=|of=)",  # dd with input/output files
        r"\bmkfifo\b",  # Named pipe creation
        r"\bmknod\b",  # Device node creation
        r"\bmount\b",  # Mount commands
        r"\bumount\b",  # Unmount commands
        r"\bchroot\b",  # Change root
        r"\bsu\b",  # Switch user
        r"\bsudo\b",  # Sudo (unless explicitly allowed)
        r"\bwget\s.*-O\s+/",  # wget output to root
        r"\bcurl\s.*-o\s+/",  # curl output to root
    ]


def _default_allowed_directories() -> set[str]:
    """Return the default set of allowed working directories."""
    return {str(Path.cwd()), str(Path.home())}


# ---------------------------------------------------------------------------
# Security Configuration
# ---------------------------------------------------------------------------
@dataclass
class ShellSecurityConfig:
    """Configuration for shell command security.

    Attributes:
        allowlist_mode: Whether to use allowlist (True) or denylist (False) approach.
        max_command_length: Maximum allowed command length in characters.
        max_args: Maximum number of arguments allowed.
        allowed_commands: Set of allowed commands when in allowlist mode.
        denied_patterns: List of regex patterns to deny when in denylist mode.
        allowed_directories: Set of allowed working directories.
        allow_sudo: Whether sudo commands are allowed.
        allow_pipes: Whether pipe operators are allowed.
        allow_redirects: Whether file redirection operators are allowed.
        allow_background: Whether background execution (&) is allowed.
        allow_subshells: Whether subshell execution ($(...) or `...`) is allowed.
        allow_env_vars: Whether environment variable expansion is allowed.
    """

    allowlist_mode: bool = True
    max_command_length: int = _DEFAULT_MAX_COMMAND_LENGTH
    max_args: int = _DEFAULT_MAX_ARGS
    allowed_commands: set[str] = None  # type: ignore[assignment]
    denied_patterns: list[str] = None  # type: ignore[assignment]
    allowed_directories: set[str] = None  # type: ignore[assignment]
    allow_sudo: bool = False
    allow_pipes: bool = True
    allow_redirects: bool = True
    allow_background: bool = False
    allow_subshells: bool = False
    allow_env_vars: bool = True

    def __post_init__(self: ShellSecurityConfig) -> None:
        """Initialize default values for mutable fields."""
        if self.allowed_commands is None:
            self.allowed_commands = _default_allowed_commands()
        if self.denied_patterns is None:
            self.denied_patterns = _default_denied_patterns()
        if self.allowed_directories is None:
            self.allowed_directories = _default_allowed_directories()


# ---------------------------------------------------------------------------
# Command parsing (extracted from ShellSecurityValidator — Feature Envy fix)
# ---------------------------------------------------------------------------


def _parse_command(command: str) -> dict[str, str | bool | list[str]]:
    """Parse a command string into components for security validation.

    Args:
        command: Command string to parse.

    Returns:
        Dictionary with parsed components.

    Raises:
        ValueError: If command cannot be safely parsed.
    """
    result: dict[str, str | bool | list[str]] = {
        "original": command,
        "has_pipes": "|" in command,
        "has_redirects": any(op in command for op in [">", ">>", "<", "2>", "&>"]),
        "has_background": command.strip().endswith("&"),
        "has_subshells": any(pattern in command for pattern in ["$(", "`"]),
        "has_sudo": command.strip().startswith("sudo "),
        "tokens": [],
    }
    try:
        result["tokens"] = shlex.split(command)
    except ValueError:
        result["tokens"] = command.split()
    return result


# ---------------------------------------------------------------------------
# Validation helpers (extracted from _validate_parsed_command — C901 fix)
# ---------------------------------------------------------------------------


def _collect_denied_pattern_errors(
    command: str,
    denied_patterns: list[str],
) -> list[str]:
    """Return error messages for each denied pattern matched in command."""
    return [
        f"Command matches denied pattern: {pattern}"
        for pattern in denied_patterns
        if re.search(pattern, command, re.IGNORECASE)
    ]


def _collect_feature_flag_errors(
    parsed: dict[str, str | bool | list[str]],
    config: ShellSecurityConfig,
) -> list[str]:
    """Return error messages for any disallowed shell features in parsed."""
    checks: list[tuple[bool, bool, str]] = [
        (bool(parsed["has_sudo"]), config.allow_sudo, "sudo commands are not allowed"),
        (bool(parsed["has_pipes"]), config.allow_pipes, "Pipe operators are not allowed"),
        (
            bool(parsed["has_redirects"]),
            config.allow_redirects,
            "File redirection operators are not allowed",
        ),
        (
            bool(parsed["has_background"]),
            config.allow_background,
            "Background execution (&) is not allowed",
        ),
        (
            bool(parsed["has_subshells"]),
            config.allow_subshells,
            "Subshell execution is not allowed",
        ),
    ]
    return [msg for active, allowed, msg in checks if active and not allowed]


def _collect_token_constraint_errors(
    tokens: list[str],
    config: ShellSecurityConfig,
) -> list[str]:
    """Return error messages for token-level constraint violations."""
    errors: list[str] = []
    if len(tokens) > config.max_args:
        errors.append(f"Command has too many arguments (max: {config.max_args})")
    if tokens and config.allowlist_mode and tokens[0] not in config.allowed_commands:
        errors.append(f"Command '{tokens[0]}' is not in allowed commands list")
    return errors


# ---------------------------------------------------------------------------
# Working-directory check helper (extracted from validate_command)
# ---------------------------------------------------------------------------


def _check_working_directory(cwd: str, allowed_directories: set[str]) -> list[str]:
    """Return an error list if cwd is not within any allowed directory."""
    cwd_path = Path(cwd).resolve()
    for allowed_dir in allowed_directories:
        allowed_path = Path(allowed_dir).resolve()
        if cwd_path == allowed_path or str(cwd_path).startswith(str(allowed_path) + os.sep):
            return []
    return [f"Working directory '{cwd}' is not in allowed directories"]


# ---------------------------------------------------------------------------
# Command basic-checks helper (extracted from validate_command)
# ---------------------------------------------------------------------------


def _check_command_basics(command: str, max_command_length: int) -> list[str]:
    """Return error messages for length and null-byte violations."""
    errors: list[str] = []
    if len(command) > max_command_length:
        errors.append(f"Command exceeds maximum length of {max_command_length}")
    if "\x00" in command:
        errors.append("Command contains null bytes")
    return errors


# ---------------------------------------------------------------------------
# Security level applier (extracted from SecureShellTool — Feature Envy fix)
# ---------------------------------------------------------------------------


def _apply_strict_security(adjusted: ShellSecurityConfig) -> None:
    """Apply strict-mode constraints to adjusted config in place."""
    adjusted.allowlist_mode = True
    adjusted.allow_sudo = False
    adjusted.allow_pipes = False
    adjusted.allow_background = False
    adjusted.allow_subshells = False
    adjusted.max_command_length = _STRICT_MAX_COMMAND_LENGTH
    adjusted.max_args = _STRICT_MAX_ARGS
    adjusted.allowed_commands = {
        "echo",
        "ls",
        "cat",
        "pwd",
        "mkdir",
        "rmdir",
        "cp",
        "mv",
        "rm",
        "touch",
        "chmod",
        "stat",
        "head",
        "tail",
        "wc",
        "grep",
        "find",
    }


def _apply_moderate_security(adjusted: ShellSecurityConfig) -> None:
    """Apply moderate-mode constraints to adjusted config in place."""
    adjusted.allowlist_mode = True
    adjusted.allow_sudo = False
    adjusted.allow_pipes = True
    adjusted.allow_redirects = True
    adjusted.allow_background = False
    adjusted.allow_subshells = False
    adjusted.max_command_length = _MODERATE_MAX_COMMAND_LENGTH
    adjusted.max_args = _MODERATE_MAX_ARGS


def _apply_permissive_security(adjusted: ShellSecurityConfig) -> None:
    """Apply permissive-mode constraints to adjusted config in place."""
    adjusted.allowlist_mode = False
    adjusted.allow_sudo = True
    adjusted.allow_pipes = True
    adjusted.allow_redirects = True
    adjusted.allow_background = True
    adjusted.allow_subshells = True
    adjusted.max_command_length = _PERMISSIVE_MAX_COMMAND_LENGTH
    adjusted.max_args = _PERMISSIVE_MAX_ARGS


def _apply_security_level(
    config: ShellSecurityConfig,
    level: Literal["strict", "moderate", "permissive"],
) -> ShellSecurityConfig:
    """Return a copy of config with adjustments for the given security level.

    Args:
        config: Base security configuration.
        level: Security level to apply.

    Returns:
        Adjusted configuration copy.
    """
    adjusted = copy.copy(config)
    match level:
        case "strict":
            _apply_strict_security(adjusted)
        case "moderate":
            _apply_moderate_security(adjusted)
        case "permissive":
            _apply_permissive_security(adjusted)
    return adjusted


# ---------------------------------------------------------------------------
# Parameters schema (extracted from SecureShellTool.parameters — Long Method)
# ---------------------------------------------------------------------------

_SHELL_SECURE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Shell command to execute (validated for security)",
        },
        "timeout": {
            "type": "integer",
            "description": (
                "Command timeout in seconds. Defaults to 3600 (1 hour). Use 0 for no timeout."
            ),
        },
        "cwd": {
            "type": "string",
            "description": "Working directory for the command",
            "default": None,
        },
        "interactive": {
            "type": "boolean",
            "description": (
                "Enable interactive mode for sudo commands that require password input. "
                "Only works when running in TUI mode with a terminal."
            ),
            "default": False,
        },
        "security_level": {
            "type": "string",
            "description": "Security level: 'strict', 'moderate', or 'permissive'",
            "default": "moderate",
            "enum": ["strict", "moderate", "permissive"],
        },
        "background": {
            "type": "boolean",
            "default": True,
            "description": "Run as a tracked background task; false waits for output.",
        },
    },
    "required": ["command"],
}


# ---------------------------------------------------------------------------
# Validation result helpers (extracted from SecureShellTool.execute)
# ---------------------------------------------------------------------------


def _build_validation_error_result(errors: list[str]) -> ToolResult:
    """Build a ToolResult representing a command validation failure."""
    error_msg = "Command validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
    return ToolResult(
        content=error_msg,
        success=False,
        error="Command validation failed",
    )


# ---------------------------------------------------------------------------
# Security Validation
# ---------------------------------------------------------------------------
class ShellSecurityValidator:
    """Validates shell commands for security compliance."""

    def __init__(
        self: ShellSecurityValidator,
        config: ShellSecurityConfig | None = None,
    ) -> None:
        """Initialize validator with configuration.

        Args:
            config: Security configuration. Uses defaults if None.
        """
        self.config = config or ShellSecurityConfig()

    def validate_command(
        self: ShellSecurityValidator,
        command: str,
        cwd: str | None = None,
    ) -> list[str]:
        """Validate a shell command for security.

        Args:
            command: The command string to validate.
            cwd: Working directory for the command.

        Returns:
            List of validation errors. Empty list means command is valid.

        Raises:
            ValueError: If command is None or empty.
        """
        if command is None:
            msg = "Command cannot be None"
            raise ValueError(msg)
        if not command.strip():
            msg = "Command cannot be empty"
            raise ValueError(msg)

        errors = _check_command_basics(command, self.config.max_command_length)

        if cwd:
            errors.extend(_check_working_directory(cwd, self.config.allowed_directories))

        try:
            parsed = _parse_command(command)
            errors.extend(self._validate_parsed_command(parsed))
        except ValueError as e:
            errors.append(f"Command parsing failed: {e}")

        return errors

    def _validate_parsed_command(
        self: ShellSecurityValidator,
        parsed: dict[str, str | bool | list[str]],
    ) -> list[str]:
        """Validate parsed command components against security config.

        Args:
            parsed: Parsed command dictionary from _parse_command.

        Returns:
            List of validation errors.
        """
        command = str(parsed["original"])
        errors = _collect_denied_pattern_errors(command, self.config.denied_patterns)
        errors.extend(_collect_feature_flag_errors(parsed, self.config))
        tokens = parsed["tokens"]
        if isinstance(tokens, list):
            errors.extend(_collect_token_constraint_errors(tokens, self.config))
        return errors

    def sanitize_command(self: ShellSecurityValidator, command: str) -> str:
        """Sanitize a command by removing dangerous characters.

        Note: This should be used as a last resort. Prefer validation and
        rejection over sanitization.

        Args:
            command: Command to sanitize.

        Returns:
            Sanitized command.
        """
        sanitized = command.replace("\x00", "")
        sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", sanitized)
        if len(sanitized) > self.config.max_command_length:
            sanitized = sanitized[: self.config.max_command_length]
        return sanitized


# ---------------------------------------------------------------------------
# Secure Shell Tool
# ---------------------------------------------------------------------------
class SecureShellTool(Tool):
    """Secure shell tool with command injection protection.

    This tool wraps the standard shell tool with security validation
    to prevent command injection attacks and other security issues.
    """

    DEFAULT_CONFIG: ClassVar[ShellSecurityConfig] = ShellSecurityConfig()

    def __init__(
        self: SecureShellTool,
        config: ShellSecurityConfig | None = None,
        wrapped_tool: ShellTool | None = None,
    ) -> None:
        """Initialize secure shell tool.

        Args:
            config: Security configuration. Uses defaults if None.
            wrapped_tool: Underlying shell tool to wrap. Creates new if None.
        """
        self.config = config or self.DEFAULT_CONFIG
        self.validator = ShellSecurityValidator(self.config)
        self.wrapped_tool = wrapped_tool or ShellTool()

    def bind_runtime(self, *, project_root: Path | None = None, **kwargs: object) -> None:
        """Keep wrapped shell jobs in the same project as the task tools."""
        self.wrapped_tool.bind_runtime(project_root=project_root, **kwargs)

    @property
    def name(self: SecureShellTool) -> str:
        """Tool name."""
        return "shell_secure"

    @property
    def description(self: SecureShellTool) -> str:
        """Tool description."""
        return (
            "Execute a shell command with security validation to prevent "
            "command injection attacks. Runs in the background by default; use task_get, "
            "task_output, task_list and task_stop to track jobs, or background=false to wait."
        )

    parameters = _SHELL_SECURE_PARAMETERS

    @property
    def kind(self: SecureShellTool) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]
        self: SecureShellTool,
        command: str = "",
        timeout: int | None = None,
        cwd: str | None = None,
        security_level: Literal["strict", "moderate", "permissive"] = "moderate",
        background: bool = True,
        **kwargs: object,
    ) -> ToolResult:
        """Execute shell command with security validation.

        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds.
            cwd: Working directory for the command.
            security_level: Security validation level.
            background: Start a tracked task, or wait for completion when false.
            **kwargs: Additional arguments.

        Returns:
            ToolResult with command output or error.
        """
        effective_config = _apply_security_level(self.config, security_level)
        validator = ShellSecurityValidator(effective_config)

        try:
            errors = validator.validate_command(command, cwd)
            if errors:
                return _build_validation_error_result(errors)
        except ValueError as e:
            return ToolResult(
                content=f"Invalid command: {e}",
                success=False,
                error=str(e),
            )

        sanitized_command = validator.sanitize_command(command)
        return await self.wrapped_tool.execute(
            command=sanitized_command,
            timeout=timeout,
            cwd=cwd,
            background=background,
            **kwargs,
        )
