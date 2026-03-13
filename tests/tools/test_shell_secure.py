"""Comprehensive tests for shell_secure.py — targets 100% coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from henchman.tools.base import ToolKind, ToolResult
from henchman.tools.security.shell_secure import (
    SecureShellTool,
    ShellSecurityConfig,
    ShellSecurityValidator,
    _apply_moderate_security,
    _apply_permissive_security,
    _apply_security_level,
    _apply_strict_security,
    _build_validation_error_result,
    _check_command_basics,
    _check_working_directory,
    _collect_denied_pattern_errors,
    _collect_feature_flag_errors,
    _collect_token_constraint_errors,
    _default_allowed_commands,
    _default_allowed_directories,
    _default_denied_patterns,
    _parse_command,
)

# ---------------------------------------------------------------------------
# Default configuration builders
# ---------------------------------------------------------------------------


class TestDefaultAllowedCommands:
    """Tests for _default_allowed_commands."""

    def test_returns_set(self) -> None:
        """Returns a set."""
        assert isinstance(_default_allowed_commands(), set)

    def test_contains_common_commands(self) -> None:
        """Contains expected common commands."""
        cmds = _default_allowed_commands()
        for cmd in ("echo", "ls", "cat", "grep", "find", "pwd", "git", "python3"):
            assert cmd in cmds

    def test_each_call_returns_new_set(self) -> None:
        """Each call returns a fresh set (mutable isolation)."""
        a = _default_allowed_commands()
        b = _default_allowed_commands()
        assert a is not b


class TestDefaultDeniedPatterns:
    """Tests for _default_denied_patterns."""

    def test_returns_list(self) -> None:
        """Returns a list."""
        assert isinstance(_default_denied_patterns(), list)

    def test_contains_shell_pipe_patterns(self) -> None:
        """Contains pipe-to-shell patterns."""
        patterns = _default_denied_patterns()
        assert any("bash" in p for p in patterns)

    def test_each_call_returns_new_list(self) -> None:
        """Each call returns a fresh list."""
        a = _default_denied_patterns()
        b = _default_denied_patterns()
        assert a is not b


class TestDefaultAllowedDirectories:
    """Tests for _default_allowed_directories."""

    def test_returns_set(self) -> None:
        """Returns a set."""
        assert isinstance(_default_allowed_directories(), set)

    def test_contains_cwd_and_home(self) -> None:
        """Contains cwd and home directory."""
        dirs = _default_allowed_directories()
        assert str(Path.cwd()) in dirs
        assert str(Path.home()) in dirs


# ---------------------------------------------------------------------------
# ShellSecurityConfig
# ---------------------------------------------------------------------------


class TestShellSecurityConfig:
    """Tests for ShellSecurityConfig dataclass."""

    def test_defaults_populated_on_init(self) -> None:
        """__post_init__ populates None fields with defaults."""
        cfg = ShellSecurityConfig()
        assert isinstance(cfg.allowed_commands, set)
        assert isinstance(cfg.denied_patterns, list)
        assert isinstance(cfg.allowed_directories, set)

    def test_custom_values_not_overwritten(self) -> None:
        """Explicitly supplied values are not replaced."""
        custom_cmds: set[str] = {"echo"}
        custom_patterns: list[str] = [r"foo"]
        custom_dirs: set[str] = {"/tmp"}
        cfg = ShellSecurityConfig(
            allowed_commands=custom_cmds,
            denied_patterns=custom_patterns,
            allowed_directories=custom_dirs,
        )
        assert cfg.allowed_commands is custom_cmds
        assert cfg.denied_patterns is custom_patterns
        assert cfg.allowed_directories is custom_dirs

    def test_default_flags(self) -> None:
        """Default flag values are correct."""
        cfg = ShellSecurityConfig()
        assert cfg.allowlist_mode is True
        assert cfg.allow_sudo is False
        assert cfg.allow_pipes is True
        assert cfg.allow_redirects is True
        assert cfg.allow_background is False
        assert cfg.allow_subshells is False
        assert cfg.allow_env_vars is True

    def test_max_defaults(self) -> None:
        """Max command length and max args have expected defaults."""
        cfg = ShellSecurityConfig()
        assert cfg.max_command_length == 4096
        assert cfg.max_args == 50


# ---------------------------------------------------------------------------
# _parse_command
# ---------------------------------------------------------------------------


class TestParseCommand:
    """Tests for _parse_command."""

    def test_simple_command(self) -> None:
        """Parses a simple command correctly."""
        parsed = _parse_command("echo hello")
        assert parsed["original"] == "echo hello"
        assert parsed["has_pipes"] is False
        assert parsed["has_redirects"] is False
        assert parsed["has_background"] is False
        assert parsed["has_subshells"] is False
        assert parsed["has_sudo"] is False
        assert parsed["tokens"] == ["echo", "hello"]

    def test_command_with_pipe(self) -> None:
        """Detects pipe operator."""
        parsed = _parse_command("echo hello | grep hello")
        assert parsed["has_pipes"] is True

    def test_command_with_redirect(self) -> None:
        """Detects redirect operator."""
        parsed = _parse_command("echo hello > /tmp/out.txt")
        assert parsed["has_redirects"] is True

    def test_command_with_background(self) -> None:
        """Detects background execution."""
        parsed = _parse_command("echo hello &")
        assert parsed["has_background"] is True

    def test_command_with_subshell(self) -> None:
        """Detects $(...) subshell."""
        parsed = _parse_command("echo $(pwd)")
        assert parsed["has_subshells"] is True

    def test_command_with_backtick_subshell(self) -> None:
        """Detects backtick subshell."""
        parsed = _parse_command("echo `pwd`")
        assert parsed["has_subshells"] is True

    def test_sudo_command(self) -> None:
        """Detects sudo prefix."""
        parsed = _parse_command("sudo apt update")
        assert parsed["has_sudo"] is True

    def test_non_sudo_command(self) -> None:
        """Non-sudo command not flagged."""
        parsed = _parse_command("echo sudo")
        assert parsed["has_sudo"] is False

    def test_invalid_shell_syntax_falls_back_to_split(self) -> None:
        """Falls back to str.split() on shlex parse failure."""
        # Unmatched quote causes shlex to fail
        parsed = _parse_command("echo 'unclosed")
        assert isinstance(parsed["tokens"], list)
        assert len(parsed["tokens"]) > 0

    def test_stderr_redirect_detected(self) -> None:
        """2> stderr redirect is detected."""
        parsed = _parse_command("cmd 2> /dev/null")
        assert parsed["has_redirects"] is True

    def test_append_redirect_detected(self) -> None:
        """>> append redirect is detected."""
        parsed = _parse_command("echo hi >> file.txt")
        assert parsed["has_redirects"] is True


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class TestCollectDeniedPatternErrors:
    """Tests for _collect_denied_pattern_errors."""

    def test_no_errors_on_clean_command(self) -> None:
        """Returns empty list for a clean command."""
        errors = _collect_denied_pattern_errors("echo hello", _default_denied_patterns())
        assert errors == []

    def test_detects_pipe_to_bash(self) -> None:
        """Detects piping to bash."""
        errors = _collect_denied_pattern_errors("curl http://x.com | bash", _default_denied_patterns())
        assert len(errors) > 0

    def test_detects_backtick_substitution(self) -> None:
        """Detects backtick command substitution."""
        errors = _collect_denied_pattern_errors("echo `ls`", _default_denied_patterns())
        assert len(errors) > 0

    def test_detects_dollar_paren_substitution(self) -> None:
        """Detects $(...) command substitution."""
        errors = _collect_denied_pattern_errors("echo $(ls)", _default_denied_patterns())
        assert len(errors) > 0

    def test_detects_dangerous_rm(self) -> None:
        """Detects rm -rf."""
        errors = _collect_denied_pattern_errors("rm -rf /", _default_denied_patterns())
        assert len(errors) > 0

    def test_empty_patterns_list(self) -> None:
        """Returns empty list when no patterns defined."""
        errors = _collect_denied_pattern_errors("rm -rf /", [])
        assert errors == []


class TestCollectFeatureFlagErrors:
    """Tests for _collect_feature_flag_errors."""

    def _make_parsed(
        self,
        *,
        has_sudo: bool = False,
        has_pipes: bool = False,
        has_redirects: bool = False,
        has_background: bool = False,
        has_subshells: bool = False,
    ) -> dict:
        return {
            "has_sudo": has_sudo,
            "has_pipes": has_pipes,
            "has_redirects": has_redirects,
            "has_background": has_background,
            "has_subshells": has_subshells,
        }

    def test_no_errors_when_all_allowed(self) -> None:
        """Returns empty list when everything is permitted."""
        cfg = ShellSecurityConfig(
            allow_sudo=True,
            allow_pipes=True,
            allow_redirects=True,
            allow_background=True,
            allow_subshells=True,
        )
        parsed = self._make_parsed(
            has_sudo=True, has_pipes=True, has_redirects=True,
            has_background=True, has_subshells=True,
        )
        assert _collect_feature_flag_errors(parsed, cfg) == []

    def test_sudo_not_allowed(self) -> None:
        """Returns error when sudo is used but not allowed."""
        cfg = ShellSecurityConfig(allow_sudo=False)
        parsed = self._make_parsed(has_sudo=True)
        errors = _collect_feature_flag_errors(parsed, cfg)
        assert any("sudo" in e.lower() for e in errors)

    def test_pipes_not_allowed(self) -> None:
        """Returns error when pipe is used but not allowed."""
        cfg = ShellSecurityConfig(allow_pipes=False)
        parsed = self._make_parsed(has_pipes=True)
        errors = _collect_feature_flag_errors(parsed, cfg)
        assert any("pipe" in e.lower() for e in errors)

    def test_redirects_not_allowed(self) -> None:
        """Returns error when redirect is used but not allowed."""
        cfg = ShellSecurityConfig(allow_redirects=False)
        parsed = self._make_parsed(has_redirects=True)
        errors = _collect_feature_flag_errors(parsed, cfg)
        assert any("redirect" in e.lower() for e in errors)

    def test_background_not_allowed(self) -> None:
        """Returns error when background execution is used but not allowed."""
        cfg = ShellSecurityConfig(allow_background=False)
        parsed = self._make_parsed(has_background=True)
        errors = _collect_feature_flag_errors(parsed, cfg)
        assert any("background" in e.lower() for e in errors)

    def test_subshells_not_allowed(self) -> None:
        """Returns error when subshell is used but not allowed."""
        cfg = ShellSecurityConfig(allow_subshells=False)
        parsed = self._make_parsed(has_subshells=True)
        errors = _collect_feature_flag_errors(parsed, cfg)
        assert any("subshell" in e.lower() for e in errors)


class TestCollectTokenConstraintErrors:
    """Tests for _collect_token_constraint_errors."""

    def test_no_errors_for_valid_tokens(self) -> None:
        """Returns empty list for valid tokens."""
        cfg = ShellSecurityConfig()
        tokens = ["echo", "hello"]
        assert _collect_token_constraint_errors(tokens, cfg) == []

    def test_too_many_args(self) -> None:
        """Returns error when token count exceeds max_args."""
        cfg = ShellSecurityConfig(max_args=2)
        tokens = ["echo", "a", "b", "c"]
        errors = _collect_token_constraint_errors(tokens, cfg)
        assert any("too many" in e.lower() for e in errors)

    def test_command_not_in_allowlist(self) -> None:
        """Returns error when command not in allowlist."""
        cfg = ShellSecurityConfig(
            allowlist_mode=True,
            allowed_commands={"echo", "ls"},
        )
        errors = _collect_token_constraint_errors(["curl", "http://example.com"], cfg)
        assert any("not in allowed" in e.lower() for e in errors)

    def test_denylist_mode_skips_allowlist_check(self) -> None:
        """When allowlist_mode=False, allowlist check is skipped."""
        cfg = ShellSecurityConfig(allowlist_mode=False)
        errors = _collect_token_constraint_errors(["curl", "http://example.com"], cfg)
        assert not any("not in allowed" in e.lower() for e in errors)

    def test_empty_tokens(self) -> None:
        """Empty token list produces no errors."""
        cfg = ShellSecurityConfig(max_args=50)
        assert _collect_token_constraint_errors([], cfg) == []


class TestCheckWorkingDirectory:
    """Tests for _check_working_directory."""

    def test_allowed_cwd(self, tmp_path: Path) -> None:
        """No errors for allowed directory."""
        errors = _check_working_directory(str(tmp_path), {str(tmp_path)})
        assert errors == []

    def test_subdirectory_is_allowed(self, tmp_path: Path) -> None:
        """Subdirectory of an allowed directory is permitted."""
        sub = tmp_path / "sub"
        sub.mkdir()
        errors = _check_working_directory(str(sub), {str(tmp_path)})
        assert errors == []

    def test_disallowed_cwd(self, tmp_path: Path) -> None:
        """Returns error for directory outside allowed set."""
        errors = _check_working_directory("/not/allowed", {str(tmp_path)})
        assert len(errors) > 0
        assert "not in allowed" in errors[0].lower() or "Working directory" in errors[0]


class TestCheckCommandBasics:
    """Tests for _check_command_basics."""

    def test_clean_command(self) -> None:
        """No errors for clean, short command."""
        assert _check_command_basics("echo hi", 4096) == []

    def test_command_too_long(self) -> None:
        """Returns error when command exceeds max length."""
        errors = _check_command_basics("x" * 10, 5)
        assert any("maximum length" in e.lower() or "exceeds" in e.lower() for e in errors)

    def test_null_byte_detected(self) -> None:
        """Returns error when command contains null byte."""
        errors = _check_command_basics("echo\x00hello", 4096)
        assert any("null" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Security level appliers
# ---------------------------------------------------------------------------


class TestApplyStrictSecurity:
    """Tests for _apply_strict_security."""

    def test_strict_disables_pipes(self) -> None:
        """Strict mode disables pipes."""
        cfg = ShellSecurityConfig()
        _apply_strict_security(cfg)
        assert cfg.allow_pipes is False

    def test_strict_disables_redirects(self) -> None:
        """Strict mode disables redirects."""
        cfg = ShellSecurityConfig()
        _apply_strict_security(cfg)
        assert cfg.allow_redirects is False

    def test_strict_disables_sudo(self) -> None:
        """Strict mode disables sudo."""
        cfg = ShellSecurityConfig()
        _apply_strict_security(cfg)
        assert cfg.allow_sudo is False

    def test_strict_sets_lower_limits(self) -> None:
        """Strict mode applies lower command length and arg limits."""
        cfg = ShellSecurityConfig()
        _apply_strict_security(cfg)
        assert cfg.max_command_length == 1024
        assert cfg.max_args == 20

    def test_strict_allowlist_mode(self) -> None:
        """Strict mode enables allowlist."""
        cfg = ShellSecurityConfig()
        _apply_strict_security(cfg)
        assert cfg.allowlist_mode is True

    def test_strict_allowed_commands_is_subset(self) -> None:
        """Strict mode uses a restricted command set."""
        cfg = ShellSecurityConfig()
        _apply_strict_security(cfg)
        assert "echo" in cfg.allowed_commands
        assert "curl" not in cfg.allowed_commands


class TestApplyModerateSecurity:
    """Tests for _apply_moderate_security."""

    def test_moderate_allows_pipes(self) -> None:
        """Moderate mode allows pipes."""
        cfg = ShellSecurityConfig()
        _apply_moderate_security(cfg)
        assert cfg.allow_pipes is True

    def test_moderate_disables_sudo(self) -> None:
        """Moderate mode disables sudo."""
        cfg = ShellSecurityConfig()
        _apply_moderate_security(cfg)
        assert cfg.allow_sudo is False

    def test_moderate_disables_background(self) -> None:
        """Moderate mode disables background execution."""
        cfg = ShellSecurityConfig()
        _apply_moderate_security(cfg)
        assert cfg.allow_background is False

    def test_moderate_sets_limits(self) -> None:
        """Moderate mode applies moderate limits."""
        cfg = ShellSecurityConfig()
        _apply_moderate_security(cfg)
        assert cfg.max_command_length == 2048
        assert cfg.max_args == 30


class TestApplyPermissiveSecurity:
    """Tests for _apply_permissive_security."""

    def test_permissive_allows_sudo(self) -> None:
        """Permissive mode allows sudo."""
        cfg = ShellSecurityConfig()
        _apply_permissive_security(cfg)
        assert cfg.allow_sudo is True

    def test_permissive_allows_background(self) -> None:
        """Permissive mode allows background."""
        cfg = ShellSecurityConfig()
        _apply_permissive_security(cfg)
        assert cfg.allow_background is True

    def test_permissive_allows_subshells(self) -> None:
        """Permissive mode allows subshells."""
        cfg = ShellSecurityConfig()
        _apply_permissive_security(cfg)
        assert cfg.allow_subshells is True

    def test_permissive_disables_allowlist(self) -> None:
        """Permissive mode disables allowlist."""
        cfg = ShellSecurityConfig()
        _apply_permissive_security(cfg)
        assert cfg.allowlist_mode is False

    def test_permissive_sets_high_limits(self) -> None:
        """Permissive mode applies high limits."""
        cfg = ShellSecurityConfig()
        _apply_permissive_security(cfg)
        assert cfg.max_command_length == 8192
        assert cfg.max_args == 100


class TestApplySecurityLevel:
    """Tests for _apply_security_level."""

    def test_returns_copy_not_original(self) -> None:
        """Returns a new config object, not the original."""
        cfg = ShellSecurityConfig()
        result = _apply_security_level(cfg, "strict")
        assert result is not cfg

    def test_strict_level(self) -> None:
        """Applies strict constraints."""
        cfg = ShellSecurityConfig()
        result = _apply_security_level(cfg, "strict")
        assert result.allow_pipes is False

    def test_moderate_level(self) -> None:
        """Applies moderate constraints."""
        cfg = ShellSecurityConfig()
        result = _apply_security_level(cfg, "moderate")
        assert result.max_command_length == 2048

    def test_permissive_level(self) -> None:
        """Applies permissive constraints."""
        cfg = ShellSecurityConfig()
        result = _apply_security_level(cfg, "permissive")
        assert result.allow_sudo is True

    def test_unknown_level_returns_copy_unchanged(self) -> None:
        """Returns a copy of config unchanged when level doesn't match any case."""
        cfg = ShellSecurityConfig(max_args=42)
        # Pass an invalid level to exercise the no-match branch (375->377)
        result = _apply_security_level(cfg, "unknown")  # type: ignore[arg-type]
        assert result is not cfg
        assert result.max_args == 42  # Unchanged since no case matched


# ---------------------------------------------------------------------------
# _build_validation_error_result
# ---------------------------------------------------------------------------


class TestBuildValidationErrorResult:
    """Tests for _build_validation_error_result."""

    def test_returns_tool_result(self) -> None:
        """Returns a ToolResult."""
        result = _build_validation_error_result(["error one"])
        assert isinstance(result, ToolResult)

    def test_success_is_false(self) -> None:
        """Result has success=False."""
        result = _build_validation_error_result(["some error"])
        assert result.success is False

    def test_error_field_set(self) -> None:
        """Error field is set."""
        result = _build_validation_error_result(["some error"])
        assert result.error is not None

    def test_content_contains_errors(self) -> None:
        """Content lists all errors."""
        result = _build_validation_error_result(["error one", "error two"])
        assert "error one" in result.content
        assert "error two" in result.content


# ---------------------------------------------------------------------------
# ShellSecurityValidator
# ---------------------------------------------------------------------------


class TestShellSecurityValidator:
    """Tests for ShellSecurityValidator."""

    def test_init_with_default_config(self) -> None:
        """Initializes with a default config when none provided."""
        validator = ShellSecurityValidator()
        assert validator.config is not None

    def test_init_with_custom_config(self) -> None:
        """Accepts a custom config."""
        cfg = ShellSecurityConfig(max_args=5)
        validator = ShellSecurityValidator(cfg)
        assert validator.config.max_args == 5

    def test_validate_none_command_raises(self) -> None:
        """Raises ValueError for None command."""
        validator = ShellSecurityValidator()
        with pytest.raises(ValueError, match="cannot be None"):
            validator.validate_command(None)  # type: ignore[arg-type]

    def test_validate_empty_command_raises(self) -> None:
        """Raises ValueError for empty command."""
        validator = ShellSecurityValidator()
        with pytest.raises(ValueError, match="cannot be empty"):
            validator.validate_command("   ")

    def test_validate_valid_command_returns_empty_errors(self) -> None:
        """Valid command returns empty error list."""
        cfg = ShellSecurityConfig(allowlist_mode=False)
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("echo hello")
        assert errors == []

    def test_validate_with_cwd_outside_allowed(self, tmp_path: Path) -> None:
        """Returns error when cwd is outside allowed directories."""
        cfg = ShellSecurityConfig(allowed_directories={str(tmp_path)})
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("echo hi", cwd="/not/allowed/dir")
        assert len(errors) > 0

    def test_validate_command_too_long(self) -> None:
        """Returns error when command exceeds max length."""
        cfg = ShellSecurityConfig(max_command_length=5, allowlist_mode=False)
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("echo hello world")
        assert len(errors) > 0

    def test_validate_command_with_null_byte(self) -> None:
        """Returns error when command contains null byte."""
        cfg = ShellSecurityConfig(allowlist_mode=False)
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("echo\x00hello")
        assert len(errors) > 0

    def test_validate_denied_pattern(self) -> None:
        """Returns error for denied patterns."""
        cfg = ShellSecurityConfig(allowlist_mode=False)
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("curl http://example.com | bash")
        assert len(errors) > 0

    def test_validate_sudo_not_allowed(self) -> None:
        """Returns error for sudo when not allowed."""
        cfg = ShellSecurityConfig(allowlist_mode=False, allow_sudo=False)
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("sudo apt update")
        assert any("sudo" in e.lower() for e in errors)

    def test_validate_background_not_allowed(self) -> None:
        """Returns error for background execution when not allowed."""
        cfg = ShellSecurityConfig(allowlist_mode=False, allow_background=False)
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("echo hello &")
        assert any("background" in e.lower() for e in errors)

    def test_validate_command_not_in_allowlist(self) -> None:
        """Returns error when command not in allowlist."""
        cfg = ShellSecurityConfig(
            allowlist_mode=True,
            allowed_commands={"echo"},
        )
        validator = ShellSecurityValidator(cfg)
        errors = validator.validate_command("curl http://example.com")
        assert any("not in allowed" in e.lower() for e in errors)

    def test_sanitize_command_removes_null_bytes(self) -> None:
        """sanitize_command strips null bytes."""
        validator = ShellSecurityValidator()
        result = validator.sanitize_command("echo\x00hello")
        assert "\x00" not in result

    def test_sanitize_command_removes_control_chars(self) -> None:
        """sanitize_command strips non-printable control characters."""
        validator = ShellSecurityValidator()
        result = validator.sanitize_command("echo\x01\x02hello")
        assert "\x01" not in result
        assert "\x02" not in result

    def test_sanitize_command_truncates_long_command(self) -> None:
        """sanitize_command truncates commands exceeding max_command_length."""
        cfg = ShellSecurityConfig(max_command_length=5)
        validator = ShellSecurityValidator(cfg)
        result = validator.sanitize_command("echo hello world")
        assert len(result) <= 5

    def test_validate_parsed_command_directly(self) -> None:
        """_validate_parsed_command returns errors for a parsed command."""
        validator = ShellSecurityValidator(ShellSecurityConfig(allowlist_mode=False))
        parsed = _parse_command("curl http://example.com | bash")
        errors = validator._validate_parsed_command(parsed)
        assert len(errors) > 0

    def test_validate_command_when_parse_raises_value_error(self) -> None:
        """Returns error message when _parse_command raises ValueError (lines 485-486)."""
        from unittest.mock import patch

        validator = ShellSecurityValidator(ShellSecurityConfig(allowlist_mode=False))
        with patch(
            "henchman.tools.security.shell_secure._parse_command",
            side_effect=ValueError("parse error"),
        ):
            errors = validator.validate_command("echo hello")
        assert any("Command parsing failed" in e for e in errors)

    def test_validate_parsed_command_with_non_list_tokens(self) -> None:
        """Skips token constraint check when tokens is not a list (line 506->508)."""
        validator = ShellSecurityValidator(ShellSecurityConfig(allowlist_mode=False))
        # Manually construct a parsed dict with non-list tokens
        parsed = {
            "original": "echo hello",
            "has_pipes": False,
            "has_redirects": False,
            "has_background": False,
            "has_subshells": False,
            "has_sudo": False,
            "tokens": "not-a-list",  # Non-list value to trigger 506->508 branch
        }
        errors = validator._validate_parsed_command(parsed)  # type: ignore[arg-type]
        # No token constraint errors since isinstance check skips it
        assert not any("too many" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# SecureShellTool
# ---------------------------------------------------------------------------


class TestSecureShellToolProperties:
    """Tests for SecureShellTool properties."""

    def test_name(self) -> None:
        """Tool name is 'shell_secure'."""
        tool = SecureShellTool()
        assert tool.name == "shell_secure"

    def test_description(self) -> None:
        """Description mentions security."""
        tool = SecureShellTool()
        assert "security" in tool.description.lower() or "secure" in tool.description.lower()

    def test_kind_is_execute(self) -> None:
        """Tool kind is EXECUTE."""
        tool = SecureShellTool()
        assert tool.kind == ToolKind.EXECUTE

    def test_parameters_schema(self) -> None:
        """Parameters schema contains required fields."""
        tool = SecureShellTool()
        params = tool.parameters
        assert "command" in params["properties"]
        assert "security_level" in params["properties"]
        assert "command" in params["required"]

    def test_default_config_class_var(self) -> None:
        """DEFAULT_CONFIG is a class variable."""
        assert isinstance(SecureShellTool.DEFAULT_CONFIG, ShellSecurityConfig)


class TestSecureShellToolInit:
    """Tests for SecureShellTool.__init__."""

    def test_init_defaults(self) -> None:
        """Init with no args uses default config and wrapped tool."""
        tool = SecureShellTool()
        assert tool.config is not None
        assert tool.wrapped_tool is not None

    def test_init_with_custom_config(self) -> None:
        """Init with custom config."""
        cfg = ShellSecurityConfig(max_args=5)
        tool = SecureShellTool(config=cfg)
        assert tool.config.max_args == 5

    def test_init_with_custom_wrapped_tool(self) -> None:
        """Init with custom wrapped tool."""
        from henchman.tools.builtins.shell import ShellTool

        wrapped = ShellTool(default_timeout=30)
        tool = SecureShellTool(wrapped_tool=wrapped)
        assert tool.wrapped_tool is wrapped


class TestSecureShellToolExecute:
    """Tests for SecureShellTool.execute."""

    @pytest.mark.anyio
    async def test_execute_valid_command_strict(self) -> None:
        """Executes valid command under strict security level."""
        mock_result = ToolResult(content="hello", success=True, error=None)
        tool = SecureShellTool()
        with patch.object(tool.wrapped_tool, "execute", return_value=mock_result) as mock_exec:
            result = await tool.execute(command="echo hello", security_level="strict")
            assert result.success is True
            mock_exec.assert_called_once()

    @pytest.mark.anyio
    async def test_execute_valid_command_moderate(self) -> None:
        """Executes valid command under moderate security level (default)."""
        mock_result = ToolResult(content="hello", success=True, error=None)
        tool = SecureShellTool()
        with patch.object(tool.wrapped_tool, "execute", return_value=mock_result):
            result = await tool.execute(command="echo hello", security_level="moderate")
            assert result.success is True

    @pytest.mark.anyio
    async def test_execute_valid_command_permissive(self) -> None:
        """Executes valid command under permissive security level."""
        mock_result = ToolResult(content="ok", success=True, error=None)
        tool = SecureShellTool()
        with patch.object(tool.wrapped_tool, "execute", return_value=mock_result):
            result = await tool.execute(command="echo hello", security_level="permissive")
            assert result.success is True

    @pytest.mark.anyio
    async def test_execute_empty_command_raises_validation_error(self) -> None:
        """Empty command is rejected with validation error."""
        tool = SecureShellTool()
        result = await tool.execute(command="")
        assert result.success is False
        assert result.error is not None

    @pytest.mark.anyio
    async def test_execute_none_command_raises_validation_error(self) -> None:
        """None command is rejected with validation error."""
        tool = SecureShellTool()
        result = await tool.execute(command=None)  # type: ignore[arg-type]
        assert result.success is False

    @pytest.mark.anyio
    async def test_execute_disallowed_command_strict(self) -> None:
        """Disallowed command under strict mode returns validation error."""
        tool = SecureShellTool()
        # 'curl' is not in strict mode allowlist
        result = await tool.execute(command="curl http://example.com", security_level="strict")
        assert result.success is False
        assert "validation" in result.content.lower() or "not in allowed" in result.content.lower()

    @pytest.mark.anyio
    async def test_execute_pipe_to_bash_denied(self) -> None:
        """Pipe to bash is denied."""
        tool = SecureShellTool()
        result = await tool.execute(
            command="echo x | bash", security_level="permissive"
        )
        # Under permissive mode, pipe_to_bash pattern is in denied_patterns
        assert result.success is False

    @pytest.mark.anyio
    async def test_execute_passes_timeout_to_wrapped_tool(self) -> None:
        """Timeout is forwarded to the wrapped tool."""
        mock_result = ToolResult(content="ok", success=True, error=None)
        tool = SecureShellTool()
        with patch.object(tool.wrapped_tool, "execute", return_value=mock_result) as mock_exec:
            await tool.execute(command="echo hi", timeout=60, security_level="strict")
            call_kwargs = mock_exec.call_args[1]
            assert call_kwargs.get("timeout") == 60 or mock_exec.call_args[0][1] == 60  # noqa: PLR2004

    @pytest.mark.anyio
    async def test_execute_passes_cwd_to_wrapped_tool(self, tmp_path: Path) -> None:
        """cwd is forwarded to the wrapped tool."""
        mock_result = ToolResult(content="ok", success=True, error=None)
        cfg = ShellSecurityConfig(
            allowlist_mode=False,
            allowed_directories={str(tmp_path)},
        )
        tool = SecureShellTool(config=cfg)
        with patch.object(tool.wrapped_tool, "execute", return_value=mock_result) as mock_exec:
            await tool.execute(
                command="echo hi",
                cwd=str(tmp_path),
                security_level="permissive",
            )
            mock_exec.assert_called_once()

    @pytest.mark.anyio
    async def test_execute_with_sudo_in_permissive_mode(self) -> None:
        """Sudo is allowed in permissive mode if not in denied_patterns."""
        mock_result = ToolResult(content="ok", success=True, error=None)
        # Create config with no denied patterns, permissive
        cfg = ShellSecurityConfig(
            allowlist_mode=False,
            allow_sudo=True,
            denied_patterns=[],  # No denied patterns
        )
        tool = SecureShellTool(config=cfg)
        with patch.object(tool.wrapped_tool, "execute", return_value=mock_result):
            result = await tool.execute(command="sudo echo hi", security_level="permissive")
            # In permissive mode sudo is allowed
            assert result.success is True

    @pytest.mark.anyio
    async def test_execute_background_not_allowed_by_default(self) -> None:
        """Background execution is blocked by default."""
        tool = SecureShellTool()
        result = await tool.execute(command="sleep 10 &", security_level="moderate")
        assert result.success is False

    @pytest.mark.anyio
    async def test_execute_subshell_not_allowed(self) -> None:
        """Subshell execution is blocked."""
        tool = SecureShellTool()
        result = await tool.execute(command="echo $(whoami)", security_level="moderate")
        assert result.success is False

    @pytest.mark.anyio
    async def test_execute_forwards_kwargs(self) -> None:
        """Extra kwargs are forwarded to wrapped tool."""
        mock_result = ToolResult(content="ok", success=True, error=None)
        tool = SecureShellTool()
        with patch.object(tool.wrapped_tool, "execute", return_value=mock_result) as mock_exec:
            await tool.execute(command="echo hello", security_level="strict", interactive=False)
            mock_exec.assert_called_once()
            assert "interactive" in mock_exec.call_args[1]
