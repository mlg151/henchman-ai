"""Secure shell tool implementation with command injection protection.

This module provides a secure wrapper around the shell tool that validates
and sanitizes commands to prevent command injection attacks.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import dataclass
from typing import ClassVar, Literal

from henchman.tools.base import Tool, ToolKind, ToolResult
from henchman.tools.builtins.shell import ShellTool


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
    max_command_length: int = 4096
    max_args: int = 50
    allowed_commands: set[str] = None  # type: ignore[assignment]
    denied_patterns: list[str] = None  # type: ignore[assignment]
    allowed_directories: set[str] = None  # type: ignore[assignment]
    allow_sudo: bool = False
    allow_pipes: bool = True
    allow_redirects: bool = True
    allow_background: bool = False
    allow_subshells: bool = False
    allow_env_vars: bool = True

    def __post_init__(self) -> None:
        """Initialize default values."""
        if self.allowed_commands is None:
            self.allowed_commands = {
                "echo", "ls", "cat", "grep", "find", "pwd", "cd",
                "mkdir", "rmdir", "cp", "mv", "rm", "touch", "chmod",
                "chown", "stat", "file", "head", "tail", "wc", "sort",
                "uniq", "cut", "paste", "tr", "sed", "awk", "python",
                "python3", "pip", "pip3", "git", "curl", "wget",
                "tar", "gzip", "gunzip", "zip", "unzip", "df", "du",
                "ps", "top", "kill", "killall", "pgrep", "pkill",
                "date", "time", "which", "whereis", "locate", "updatedb",
            }
        if self.denied_patterns is None:
            self.denied_patterns = [
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
                r">\s*/dev/(tcp|udp)/",  # TCP/UDP redirection
                r">\s*/proc/",  # Proc filesystem access
                r">\s*/sys/",  # Sys filesystem access
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
        if self.allowed_directories is None:
            # Default to current working directory and subdirectories
            cwd = os.getcwd()
            self.allowed_directories = {cwd, os.path.expanduser("~")}


# ---------------------------------------------------------------------------
# Security Validation
# ---------------------------------------------------------------------------
class ShellSecurityValidator:
    """Validates shell commands for security compliance."""

    def __init__(self, config: ShellSecurityConfig | None = None) -> None:
        """Initialize validator with configuration.

        Args:
            config: Security configuration. Uses defaults if None.
        """
        self.config = config or ShellSecurityConfig()

    def validate_command(self, command: str, cwd: str | None = None) -> list[str]:
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
            raise ValueError("Command cannot be None")
        if not command.strip():
            raise ValueError("Command cannot be empty")

        errors: list[str] = []

        # Basic length check
        if len(command) > self.config.max_command_length:
            errors.append(f"Command exceeds maximum length of {self.config.max_command_length}")

        # Check for null bytes
        if "\x00" in command:
            errors.append("Command contains null bytes")

        # Check working directory
        if cwd:
            cwd_path = os.path.abspath(cwd)
            allowed = False
            for allowed_dir in self.config.allowed_directories:
                allowed_dir_path = os.path.abspath(allowed_dir)
                if cwd_path.startswith(allowed_dir_path + os.sep) or cwd_path == allowed_dir_path:
                    allowed = True
                    break
            if not allowed:
                errors.append(f"Working directory '{cwd}' is not in allowed directories")

        # Parse command for deeper analysis
        try:
            parsed = self._parse_command(command)
            errors.extend(self._validate_parsed_command(parsed))
        except ValueError as e:
            errors.append(f"Command parsing failed: {e}")

        return errors

    def _parse_command(self, command: str) -> dict[str, str | bool | list[str]]:
        """Parse command into components for validation.

        Args:
            command: Command string to parse.

        Returns:
            Dictionary with parsed components.

        Raises:
            ValueError: If command cannot be safely parsed.
        """
        # Simple parsing - we don't want to use full shell parsing for security
        # This is a simplified approach that looks for dangerous patterns
        result: dict[str, str | bool | list[str]] = {
            "original": command,
            "has_pipes": "|" in command,
            "has_redirects": any(op in command for op in [">", ">>", "<", "2>", "&>"]),
            "has_background": command.strip().endswith("&"),
            "has_subshells": any(pattern in command for pattern in ["$(", "`"]),
            "has_sudo": command.strip().startswith("sudo "),
            "tokens": [],
        }

        # Simple tokenization (not full shell parsing)
        try:
            # Use shlex for basic splitting that handles quotes
            result["tokens"] = shlex.split(command)
        except ValueError:
            # Fallback to simple whitespace splitting
            result["tokens"] = command.split()

        return result

    def _validate_parsed_command(self, parsed: dict[str, str | bool | list[str]]) -> list[str]:
        """Validate parsed command components.

        Args:
            parsed: Parsed command dictionary.

        Returns:
            List of validation errors.
        """
        errors: list[str] = []

        command = str(parsed["original"])

        # Check for denied patterns
        for pattern in self.config.denied_patterns:
            if re.search(pattern, command, re.IGNORECASE):
                errors.append(f"Command matches denied pattern: {pattern}")

        # Check specific features based on configuration
        if bool(parsed["has_sudo"]) and not self.config.allow_sudo:
            errors.append("sudo commands are not allowed")

        if bool(parsed["has_pipes"]) and not self.config.allow_pipes:
            errors.append("Pipe operators are not allowed")

        if bool(parsed["has_redirects"]) and not self.config.allow_redirects:
            errors.append("File redirection operators are not allowed")

        if bool(parsed["has_background"]) and not self.config.allow_background:
            errors.append("Background execution (&) is not allowed")

        if bool(parsed["has_subshells"]) and not self.config.allow_subshells:
            errors.append("Subshell execution is not allowed")

        # Check argument count
        tokens = parsed["tokens"]
        if isinstance(tokens, list) and len(tokens) > self.config.max_args:
            errors.append(f"Command has too many arguments (max: {self.config.max_args})")

        # Allowlist/denylist checking
        if tokens and isinstance(tokens, list) and tokens:
            first_token = tokens[0]
            if self.config.allowlist_mode:
                if first_token not in self.config.allowed_commands:
                    errors.append(f"Command '{first_token}' is not in allowed commands list")
            else:
                # In denylist mode, we only block explicitly denied commands
                pass

        return errors

    def sanitize_command(self, command: str) -> str:
        """Sanitize a command by removing dangerous characters.

        Note: This should be used as a last resort. Prefer validation and
        rejection over sanitization.

        Args:
            command: Command to sanitize.

        Returns:
            Sanitized command.
        """
        # Remove null bytes
        sanitized = command.replace("\x00", "")

        # Remove control characters (except newline, tab, carriage return)
        sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", sanitized)

        # Limit length
        if len(sanitized) > self.config.max_command_length:
            sanitized = sanitized[:self.config.max_command_length]

        return sanitized


# ---------------------------------------------------------------------------
# Secure Shell Tool
# ---------------------------------------------------------------------------
class SecureShellTool(Tool):
    """Secure shell tool with command injection protection.

    This tool wraps the standard shell tool with security validation
    to prevent command injection attacks and other security issues.
    """

    # Default security configuration
    DEFAULT_CONFIG: ClassVar[ShellSecurityConfig] = ShellSecurityConfig()

    def __init__(
        self,
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

    @property
    def name(self) -> str:
        """Tool name."""
        return "shell_secure"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Execute a shell command with security validation to prevent "
            "command injection attacks. Validates commands before execution."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute (validated for security)",
                },
                "timeout": {
                    "type": "integer",
                    "description": (
                        "Command timeout in seconds. Defaults to 3600 (1 hour). "
                        "Use 0 for no timeout."
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
            },
            "required": ["command"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - EXECUTE requires confirmation."""
        return ToolKind.EXECUTE

    async def execute(  # type: ignore[override]
        self,
        command: str = "",
        timeout: int | None = None,
        cwd: str | None = None,
        security_level: Literal["strict", "moderate", "permissive"] = "moderate",
        **kwargs: object,
    ) -> ToolResult:
        """Execute shell command with security validation.

        Args:
            command: Shell command to execute.
            timeout: Command timeout in seconds.
            cwd: Working directory for the command.
            security_level: Security validation level.
            **kwargs: Additional arguments.

        Returns:
            ToolResult with command output or error.
        """
        # Apply security level adjustments
        effective_config = self._apply_security_level(self.config, security_level)

        # Create validator with effective config
        validator = ShellSecurityValidator(effective_config)

        # Validate command
        try:
            errors = validator.validate_command(command, cwd)
            if errors:
                error_msg = "Command validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                return ToolResult(
                    content=error_msg,
                    success=False,
                    error="Command validation failed",
                )
        except ValueError as e:
            return ToolResult(
                content=f"Invalid command: {e}",
                success=False,
                error=str(e),
            )

        # Sanitize command (defense in depth)
        sanitized_command = validator.sanitize_command(command)

        # Execute with wrapped tool
        return await self.wrapped_tool.execute(
            command=sanitized_command,
            timeout=timeout,
            cwd=cwd,
            **kwargs,
        )

    def _apply_security_level(
        self,
        config: ShellSecurityConfig,
        level: Literal["strict", "moderate", "permissive"],
    ) -> ShellSecurityConfig:
        """Apply security level adjustments to configuration.

        Args:
            config: Base configuration.
            level: Security level to apply.

        Returns:
            Adjusted configuration.
        """
        # Create a copy to avoid modifying the original
        import copy
        adjusted = copy.copy(config)

        if level == "strict":
            adjusted.allowlist_mode = True
            adjusted.allow_sudo = False
            adjusted.allow_pipes = False
            adjusted.allow_redirects = False
            adjusted.allow_background = False
            adjusted.allow_subshells = False
            adjusted.max_command_length = 1024
            adjusted.max_args = 20
            # Restricted command set for strict mode
            adjusted.allowed_commands = {
                "echo", "ls", "cat", "pwd", "mkdir", "rmdir",
                "cp", "mv", "rm", "touch", "chmod", "stat",
                "head", "tail", "wc", "grep", "find",
            }

        elif level == "moderate":
            adjusted.allowlist_mode = True
            adjusted.allow_sudo = False
            adjusted.allow_pipes = True
            adjusted.allow_redirects = True
            adjusted.allow_background = False
            adjusted.allow_subshells = False
            adjusted.max_command_length = 2048
            adjusted.max_args = 30

        elif level == "permissive":
            adjusted.allowlist_mode = False  # Use denylist instead
            adjusted.allow_sudo = True
            adjusted.allow_pipes = True
            adjusted.allow_redirects = True
            adjusted.allow_background = True
            adjusted.allow_subshells = True
            adjusted.max_command_length = 8192
            adjusted.max_args = 100

        return adjusted
