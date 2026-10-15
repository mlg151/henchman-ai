"""Extended tests for security.py — targets missing coverage lines."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

# Public symbols are re-exported via the __init__.py package shim.
from henchman.tools.security import (
    CommandInjectionError,
    PathTraversalError,
    SecurityError,
    SSRFError,
    atomic_read,
    atomic_write,
    sanitize_command,
    sanitize_error_message,
    validate_path,
    validate_url,
)

# Private helpers live in the underlying security.py implementation module.
# We load it directly so coverage is properly attributed to that file.
_impl_path = Path(__file__).parent.parent.parent / "src/henchman/tools/security.py"
_spec = importlib.util.spec_from_file_location("_security_impl", str(_impl_path))
_security_impl = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_security_impl)  # type: ignore[union-attr]

_check_domain_whitelist = _security_impl._check_domain_whitelist
_check_for_dangerous_patterns = _security_impl._check_for_dangerous_patterns
_check_localhost_url = _security_impl._check_localhost_url
_check_path_traversal = _security_impl._check_path_traversal
_check_private_ip_address = _security_impl._check_private_ip_address
_check_suspicious_url_patterns = _security_impl._check_suspicious_url_patterns
_check_url_scheme = _security_impl._check_url_scheme
_check_within_base_dir = _security_impl._check_within_base_dir
_find_first_matching_pattern = _security_impl._find_first_matching_pattern
_message_matches_any_keyword = _security_impl._message_matches_any_keyword
_validate_sub_commands = _security_impl._validate_sub_commands

# Exception classes from the impl module (different identity from henchman.tools.security ones
# since they come from a separate module instantiation — needed for pytest.raises on private fns).
_ImplPathTraversalError = _security_impl.PathTraversalError
_ImplCommandInjectionError = _security_impl.CommandInjectionError
_ImplSSRFError = _security_impl.SSRFError
_ImplSecurityError = _security_impl.SecurityError

# Public functions via impl for coverage attribution
_atomic_read = _security_impl.atomic_read
_atomic_write = _security_impl.atomic_write


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Tests for exception classes."""

    def test_security_error_is_exception(self) -> None:
        """SecurityError is an Exception subclass."""
        assert issubclass(SecurityError, Exception)

    def test_path_traversal_is_security_error(self) -> None:
        """PathTraversalError is a SecurityError."""
        assert issubclass(PathTraversalError, SecurityError)

    def test_command_injection_is_security_error(self) -> None:
        """CommandInjectionError is a SecurityError."""
        assert issubclass(CommandInjectionError, SecurityError)

    def test_ssrf_is_security_error(self) -> None:
        """SSRFError is a SecurityError."""
        assert issubclass(SSRFError, SecurityError)


# ---------------------------------------------------------------------------
# _find_first_matching_pattern
# ---------------------------------------------------------------------------


class TestFindFirstMatchingPattern:
    """Tests for _find_first_matching_pattern."""

    def test_returns_none_when_no_match(self) -> None:
        """Returns None when text matches no pattern."""
        result = _find_first_matching_pattern("hello world", [r"foo", r"bar"])
        assert result is None

    def test_returns_first_matching_pattern(self) -> None:
        """Returns the first matching pattern string."""
        result = _find_first_matching_pattern("hello world", [r"foo", r"world"])
        assert result == r"world"

    def test_returns_earlier_pattern_when_multiple_match(self) -> None:
        """Returns the earliest pattern in the list when multiple match."""
        result = _find_first_matching_pattern("hello world", [r"hello", r"world"])
        assert result == r"hello"

    def test_empty_patterns_returns_none(self) -> None:
        """Returns None for empty pattern list."""
        result = _find_first_matching_pattern("hello", [])
        assert result is None


# ---------------------------------------------------------------------------
# _message_matches_any_keyword
# ---------------------------------------------------------------------------


class TestMessageMatchesAnyKeyword:
    """Tests for _message_matches_any_keyword."""

    def test_returns_false_when_no_match(self) -> None:
        """Returns False when no keyword is found."""
        result = _message_matches_any_keyword("hello world", ("timeout", "network"))
        assert result is False

    def test_returns_true_when_keyword_found(self) -> None:
        """Returns True when a keyword is in the message."""
        result = _message_matches_any_keyword("Connection timeout occurred", ("timeout", "network"))
        assert result is True

    def test_case_insensitive(self) -> None:
        """Match is case insensitive."""
        result = _message_matches_any_keyword("TIMEOUT error", ("timeout",))
        assert result is True


# ---------------------------------------------------------------------------
# _check_path_traversal
# ---------------------------------------------------------------------------


class TestCheckPathTraversal:
    """Tests for _check_path_traversal."""

    def test_no_error_for_safe_path(self) -> None:
        """No exception for a safe path."""
        _check_path_traversal("/safe/path/file.txt")  # Should not raise

    def test_raises_for_dotdot_path(self) -> None:
        """Raises PathTraversalError when '..' appears as a path component."""
        with pytest.raises(_ImplPathTraversalError, match="Path traversal detected"):
            _check_path_traversal("/safe/../etc/passwd")

    def test_no_error_for_dotdot_in_filename(self) -> None:
        """No error if '..' is in filename content but not a traversal component."""
        # Path like "/safe/file..txt" has ".." in string but not as a path component
        # This is safe since Path().parts won't have ".." as a segment
        _check_path_traversal("/safe/file..txt")  # Should not raise


# ---------------------------------------------------------------------------
# _check_within_base_dir
# ---------------------------------------------------------------------------


class TestCheckWithinBaseDir:
    """Tests for _check_within_base_dir."""

    def test_no_error_when_within_base(self, tmp_path: Path) -> None:
        """No exception when path is within base directory."""
        sub = tmp_path / "subdir"
        _check_within_base_dir(sub, tmp_path)  # Should not raise

    def test_raises_when_outside_base(self, tmp_path: Path) -> None:
        """Raises PathTraversalError when path is outside base directory."""
        outside = Path("/etc/passwd")
        with pytest.raises(_ImplPathTraversalError, match="outside allowed directory"):
            _check_within_base_dir(outside, tmp_path)

    def test_exact_base_path_is_allowed(self, tmp_path: Path) -> None:
        """Exact base path itself is allowed."""
        _check_within_base_dir(tmp_path, tmp_path)  # Should not raise


# ---------------------------------------------------------------------------
# validate_path
# ---------------------------------------------------------------------------


class TestValidatePath:
    """Tests for validate_path."""

    def test_raises_for_empty_string(self) -> None:
        """Raises ValueError for empty path."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_path("")

    def test_raises_for_none_path(self) -> None:
        """Raises ValueError for falsy path."""
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_path(None)  # type: ignore[arg-type]

    def test_returns_absolute_path(self, tmp_path: Path) -> None:
        """Returns an absolute resolved Path."""
        result = validate_path(tmp_path)
        assert result.is_absolute()

    def test_path_with_base_dir_valid(self, tmp_path: Path) -> None:
        """Valid path within base_dir succeeds."""
        sub = tmp_path / "sub.txt"
        result = validate_path(sub, base_dir=tmp_path)
        assert result == sub.resolve()

    def test_path_with_base_dir_outside_raises(self, tmp_path: Path) -> None:
        """Path outside base_dir raises PathTraversalError."""
        with pytest.raises(PathTraversalError, match="outside allowed directory"):
            validate_path("/etc/passwd", base_dir=tmp_path)

    def test_path_traversal_raises(self) -> None:
        """Path traversal raises PathTraversalError."""
        with pytest.raises(PathTraversalError):
            validate_path("/safe/../etc/passwd")


# ---------------------------------------------------------------------------
# _check_for_dangerous_patterns
# ---------------------------------------------------------------------------


class TestCheckForDangerousPatterns:
    """Tests for _check_for_dangerous_patterns."""

    def test_no_error_for_safe_command(self) -> None:
        """No error for a safe command."""
        _check_for_dangerous_patterns("echo hello")

    def test_raises_for_backtick_substitution(self) -> None:
        """Raises CommandInjectionError for backtick substitution."""
        with pytest.raises(_ImplCommandInjectionError, match="Dangerous pattern detected"):
            _check_for_dangerous_patterns("echo `id`")

    def test_raises_for_dollar_paren_substitution(self) -> None:
        """Raises CommandInjectionError for $(...) substitution."""
        with pytest.raises(_ImplCommandInjectionError):
            _check_for_dangerous_patterns("echo $(id)")

    def test_raises_for_variable_expansion(self) -> None:
        """Raises CommandInjectionError for ${...} variable expansion."""
        with pytest.raises(_ImplCommandInjectionError):
            _check_for_dangerous_patterns("echo ${IFS}rm${IFS}-rf${IFS}/")

    def test_allows_redirect_to_dev_null(self) -> None:
        """Discarding command output is ordinary shell syntax."""
        _check_for_dangerous_patterns("echo test > /dev/null")

    def test_raises_for_trailing_semicolon(self) -> None:
        """Trailing semicolon should not raise (standard shell operator)."""
        _check_for_dangerous_patterns("echo hello;")  # Should not raise

    def test_raises_for_trailing_pipe(self) -> None:
        """Raises CommandInjectionError for trailing pipe."""
        with pytest.raises(_ImplCommandInjectionError):
            _check_for_dangerous_patterns("echo hello |")


# ---------------------------------------------------------------------------
# sanitize_command
# ---------------------------------------------------------------------------


class TestSanitizeCommandExtended:
    """Extended tests for sanitize_command covering missing branches."""

    def test_raises_for_empty_string(self) -> None:
        """Raises ValueError for empty command string."""
        with pytest.raises(ValueError, match="non-empty string"):
            sanitize_command("")

    def test_raises_for_none(self) -> None:
        """Raises ValueError for None."""
        with pytest.raises(ValueError, match="non-empty string"):
            sanitize_command(None)  # type: ignore[arg-type]

    def test_raises_for_non_string(self) -> None:
        """Raises ValueError for non-string types."""
        with pytest.raises(ValueError, match="non-empty string"):
            sanitize_command(123)  # type: ignore[arg-type]

    def test_raises_when_not_in_allowed_commands(self) -> None:
        """Raises CommandInjectionError when command not in allowed list."""
        with pytest.raises(CommandInjectionError, match="Command must start with one of"):
            sanitize_command("curl http://example.com", allowed_commands=["echo", "ls"])

    def test_allowed_command_passes(self) -> None:
        """Command starting with allowed prefix passes."""
        result = sanitize_command("echo hello", allowed_commands=["echo"])
        assert result == "echo hello"

    def test_raises_for_invalid_shell_syntax(self) -> None:
        """Raises CommandInjectionError for invalid shell syntax."""
        with pytest.raises(CommandInjectionError, match="Invalid shell syntax"):
            # Unmatched single quote causes shlex to fail
            sanitize_command("echo 'unclosed")

    def test_sub_commands_validated_with_pipe(self) -> None:
        """Sub-commands separated by pipe are validated recursively."""
        # Both sub-commands are valid so this should pass
        result = sanitize_command("echo hello | grep hello")
        assert "echo hello" in result

    def test_sub_commands_with_allowed_commands(self) -> None:
        """Sub-commands are checked against allowed_commands."""
        with pytest.raises(CommandInjectionError):
            sanitize_command("echo hello | curl http://x.com", allowed_commands=["echo"])

    def test_dangerous_pattern_raises_command_injection(self) -> None:
        """Dangerous pattern raises CommandInjectionError."""
        with pytest.raises(CommandInjectionError):
            sanitize_command("echo `id`")


# ---------------------------------------------------------------------------
# _validate_sub_commands
# ---------------------------------------------------------------------------


class TestValidateSubCommands:
    """Tests for _validate_sub_commands."""

    def test_valid_sub_commands_pass(self) -> None:
        """Valid sub-commands don't raise."""
        _validate_sub_commands("echo hello; echo world", None)

    def test_invalid_sub_command_raises(self) -> None:
        """Invalid sub-command propagates exception."""
        with pytest.raises(_ImplCommandInjectionError):
            _validate_sub_commands("echo hello; echo `id`", None)


# ---------------------------------------------------------------------------
# URL validation helpers
# ---------------------------------------------------------------------------


class TestCheckUrlScheme:
    """Tests for _check_url_scheme."""

    def _make_parsed(self, scheme: str, hostname: str = "example.com") -> object:
        from urllib.parse import urlparse
        url = f"{scheme}://{hostname}/path" if scheme else f"://{hostname}/path"
        return urlparse(url)

    def test_raises_for_missing_scheme(self) -> None:
        """Raises SSRFError when scheme is missing."""
        from urllib.parse import urlparse
        parsed = urlparse("//example.com/path")
        with pytest.raises(_ImplSSRFError, match="must have a scheme"):
            _check_url_scheme(parsed, ["http", "https"])

    def test_raises_for_disallowed_scheme(self) -> None:
        """Raises SSRFError for disallowed scheme."""
        from urllib.parse import urlparse
        parsed = urlparse("ftp://example.com/file")
        with pytest.raises(_ImplSSRFError, match="not allowed"):
            _check_url_scheme(parsed, ["http", "https"])

    def test_allowed_scheme_passes(self) -> None:
        """Allowed scheme does not raise."""
        from urllib.parse import urlparse
        parsed = urlparse("https://example.com")
        _check_url_scheme(parsed, ["http", "https"])  # Should not raise


class TestCheckLocalhostUrl:
    """Tests for _check_localhost_url."""

    def test_raises_for_localhost(self) -> None:
        """Raises SSRFError for localhost."""
        from urllib.parse import urlparse
        parsed = urlparse("http://localhost/path")
        with pytest.raises(_ImplSSRFError, match="Localhost URLs"):
            _check_localhost_url(parsed)

    def test_raises_for_127_0_0_1(self) -> None:
        """Raises SSRFError for 127.0.0.1."""
        from urllib.parse import urlparse
        parsed = urlparse("http://127.0.0.1/path")
        with pytest.raises(_ImplSSRFError, match="Localhost URLs"):
            _check_localhost_url(parsed)

    def test_passes_for_public_host(self) -> None:
        """No exception for public hostname."""
        from urllib.parse import urlparse
        parsed = urlparse("https://example.com/path")
        _check_localhost_url(parsed)  # Should not raise


class TestCheckPrivateIpAddress:
    """Tests for _check_private_ip_address."""

    def test_raises_for_10_x_x_x(self) -> None:
        """Raises SSRFError for 10.x.x.x private IP."""
        from urllib.parse import urlparse
        parsed = urlparse("http://10.0.0.1/path")
        with pytest.raises(_ImplSSRFError, match="Private IP"):
            _check_private_ip_address(parsed)

    def test_raises_for_192_168_x_x(self) -> None:
        """Raises SSRFError for 192.168.x.x private IP."""
        from urllib.parse import urlparse
        parsed = urlparse("http://192.168.1.1/path")
        with pytest.raises(_ImplSSRFError, match="Private IP"):
            _check_private_ip_address(parsed)

    def test_raises_for_172_16_x_x(self) -> None:
        """Raises SSRFError for 172.16.x.x private IP."""
        from urllib.parse import urlparse
        parsed = urlparse("http://172.16.0.1/path")
        with pytest.raises(_ImplSSRFError, match="Private IP"):
            _check_private_ip_address(parsed)

    def test_raises_for_169_254_x_x(self) -> None:
        """Raises SSRFError for link-local address."""
        from urllib.parse import urlparse
        parsed = urlparse("http://169.254.169.254/path")
        with pytest.raises(_ImplSSRFError, match="Private IP"):
            _check_private_ip_address(parsed)

    def test_no_raise_for_no_hostname(self) -> None:
        """No exception when parsed.hostname is None/empty."""
        from urllib.parse import urlparse
        parsed = urlparse("file:///path/to/file")
        _check_private_ip_address(parsed)  # Should not raise

    def test_passes_for_public_ip(self) -> None:
        """No exception for a public IP."""
        from urllib.parse import urlparse
        parsed = urlparse("http://8.8.8.8/path")
        _check_private_ip_address(parsed)  # Should not raise

    def test_raises_for_ipv6_private(self) -> None:
        """Raises SSRFError for IPv6 private addresses."""
        from urllib.parse import urlparse
        parsed = urlparse("http://[fc00::1]/path")
        with pytest.raises(_ImplSSRFError, match="Private IP"):
            _check_private_ip_address(parsed)


class TestCheckDomainWhitelist:
    """Tests for _check_domain_whitelist."""

    def test_raises_when_domain_not_in_whitelist(self) -> None:
        """Raises SSRFError when domain not in allowed list."""
        from urllib.parse import urlparse
        parsed = urlparse("https://evil.com/path")
        with pytest.raises(_ImplSSRFError, match="not in allowed list"):
            _check_domain_whitelist(parsed, ["example.com", "safe.com"])

    def test_passes_when_domain_in_whitelist(self) -> None:
        """No exception when domain is in allowed list."""
        from urllib.parse import urlparse
        parsed = urlparse("https://example.com/path")
        _check_domain_whitelist(parsed, ["example.com"])  # Should not raise

    def test_passes_when_no_whitelist(self) -> None:
        """No exception when allowed_domains is None."""
        from urllib.parse import urlparse
        parsed = urlparse("https://any.com/path")
        _check_domain_whitelist(parsed, None)  # Should not raise


class TestCheckSuspiciousUrlPatterns:
    """Tests for _check_suspicious_url_patterns."""

    def test_raises_for_multiple_at_symbols(self) -> None:
        """Raises SSRFError for URL with multiple @ symbols."""
        with pytest.raises(_ImplSSRFError, match="Suspicious URL pattern"):
            _check_suspicious_url_patterns("http://user@attacker.com@victim.com/path")

    def test_passes_for_clean_url(self) -> None:
        """No exception for a clean URL."""
        _check_suspicious_url_patterns("https://example.com/path?q=1")  # Should not raise

    def test_raises_for_multiple_question_marks(self) -> None:
        """Raises SSRFError for URL with multiple ? characters."""
        with pytest.raises(_ImplSSRFError, match="Suspicious URL pattern"):
            _check_suspicious_url_patterns("https://example.com/?q=1?x=2")


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------


class TestValidateUrl:
    """Tests for validate_url."""

    def test_raises_for_empty_url(self) -> None:
        """Raises ValueError for empty URL."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_url("")

    def test_raises_for_none_url(self) -> None:
        """Raises ValueError for None URL."""
        with pytest.raises(ValueError, match="non-empty string"):
            validate_url(None)  # type: ignore[arg-type]

    def test_valid_https_url_passes(self) -> None:
        """Valid HTTPS URL passes validation."""
        result = validate_url("https://example.com/path")
        assert result == "https://example.com/path"

    def test_valid_http_url_passes(self) -> None:
        """Valid HTTP URL passes validation."""
        result = validate_url("http://example.com/path")
        assert result == "http://example.com/path"

    def test_raises_for_ftp_scheme(self) -> None:
        """Raises SSRFError for FTP scheme."""
        with pytest.raises(SSRFError, match="not allowed"):
            validate_url("ftp://files.example.com/file")

    def test_raises_for_localhost(self) -> None:
        """Raises SSRFError for localhost URL."""
        with pytest.raises(SSRFError, match="Localhost"):
            validate_url("http://localhost/api")

    def test_block_localhost_false(self) -> None:
        """Allows localhost when block_localhost=False."""
        result = validate_url("http://localhost/api", block_localhost=False)
        assert result == "http://localhost/api"

    def test_raises_for_private_ip(self) -> None:
        """Raises SSRFError for private IP."""
        with pytest.raises(SSRFError, match="Private IP"):
            validate_url("http://192.168.1.1/path")

    def test_block_private_ips_false(self) -> None:
        """Allows private IPs when block_private_ips=False."""
        result = validate_url("http://192.168.1.1/path", block_private_ips=False)
        assert result == "http://192.168.1.1/path"

    def test_raises_for_domain_not_in_whitelist(self) -> None:
        """Raises SSRFError when domain not in allowed list."""
        with pytest.raises(SSRFError, match="not in allowed list"):
            validate_url(
                "https://evil.com/path",
                allowed_domains=["example.com"],
            )

    def test_passes_for_domain_in_whitelist(self) -> None:
        """Passes when domain is in allowed list."""
        result = validate_url(
            "https://example.com/path",
            allowed_domains=["example.com"],
        )
        assert result == "https://example.com/path"

    def test_raises_for_suspicious_pattern(self) -> None:
        """Raises SSRFError for suspicious URL pattern."""
        with pytest.raises(SSRFError, match="Suspicious"):
            validate_url("https://user@evil.com@victim.com/path")

    def test_custom_schemes_allowed(self) -> None:
        """Custom allowed schemes work correctly."""
        result = validate_url(
            "ftp://files.example.com/",
            allowed_schemes=["ftp", "http"],
        )
        assert result == "ftp://files.example.com/"


# ---------------------------------------------------------------------------
# sanitize_error_message
# ---------------------------------------------------------------------------


class TestSanitizeErrorMessage:
    """Tests for sanitize_error_message."""

    def test_permission_denied_returns_clean(self) -> None:
        """Permission denied error is sanitized."""
        result = sanitize_error_message("Permission denied: /secret/file")
        assert result == "Permission denied"

    def test_file_not_found_returns_clean(self) -> None:
        """File not found error is sanitized."""
        result = sanitize_error_message("No such file or directory: /tmp/missing")
        assert result == "File not found"

    def test_file_not_found_alternate_message(self) -> None:
        """'File not found' variant is sanitized."""
        result = sanitize_error_message("File not found: /tmp/missing")
        assert result == "File not found"

    def test_connection_refused_returns_clean(self) -> None:
        """Connection refused error is sanitized."""
        result = sanitize_error_message("Connection refused")
        assert result == "Connection refused"

    def test_timeout_message_sanitizes_paths(self) -> None:
        """Timeout message has paths redacted."""
        result = sanitize_error_message("Connection timed out for /internal/service")
        assert "[PATH]" in result
        assert "timed out" in result.lower()

    def test_network_message_sanitizes_paths(self) -> None:
        """Network-related message has paths redacted."""
        result = sanitize_error_message("Network error accessing /internal/api")
        assert "[PATH]" in result

    def test_generic_error_returns_sanitized_message(self) -> None:
        """Unrecognized error returns the sanitized message."""
        result = sanitize_error_message("Some weird internal error")
        assert result == "Some weird internal error"

    def test_exception_object_accepted(self) -> None:
        """Accepts an Exception object."""
        result = sanitize_error_message(ValueError("Connection refused"))
        assert result == "Connection refused"

    def test_paths_in_env_vars_redacted(self) -> None:
        """Environment variable values are redacted."""
        result = sanitize_error_message("Error: PATH=/usr/local/bin:/usr/bin")
        assert "[REDACTED]" in result or "[PATH]" in result

    def test_home_paths_redacted_before_classification(self) -> None:
        """Home paths are redacted in the message."""
        result = sanitize_error_message("Some weird error with ~/secret/file")
        assert "[HOME_PATH]" in result


# ---------------------------------------------------------------------------
# atomic_write
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """Tests for atomic_write."""

    def test_writes_content_to_file(self, tmp_path: Path) -> None:
        """Writes content to a file."""
        target = tmp_path / "output.txt"
        atomic_write(target, "hello world")
        assert target.read_text() == "hello world"

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Overwrites existing file content."""
        target = tmp_path / "output.txt"
        target.write_text("old content")
        atomic_write(target, "new content")
        assert target.read_text() == "new content"

    def test_creates_new_file(self, tmp_path: Path) -> None:
        """Creates a new file."""
        target = tmp_path / "new_file.txt"
        assert not target.exists()
        atomic_write(target, "data")
        assert target.exists()
        assert target.read_text() == "data"

    def test_raises_on_read_only_file(self, tmp_path: Path) -> None:
        """Raises PermissionError for read-only file."""
        target = tmp_path / "readonly.txt"
        target.write_text("initial")
        target.chmod(0o444)
        try:
            with pytest.raises(PermissionError):
                atomic_write(target, "new content")
        finally:
            target.chmod(0o644)  # Restore for cleanup

    def test_temp_file_cleaned_up_after_write(self, tmp_path: Path) -> None:
        """Temp file is removed after successful write."""
        target = tmp_path / "output.txt"
        atomic_write(target, "data")
        # Temp file should not exist
        temp = target.with_suffix(".txt.tmp")
        assert not temp.exists()

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Accepts a string path."""
        target = tmp_path / "output.txt"
        atomic_write(str(target), "content")
        assert target.read_text() == "content"


# ---------------------------------------------------------------------------
# atomic_read
# ---------------------------------------------------------------------------


class TestAtomicRead:
    """Tests for atomic_read."""

    def test_reads_file_content(self, tmp_path: Path) -> None:
        """Reads content from a file."""
        target = tmp_path / "input.txt"
        target.write_text("hello world")
        result = atomic_read(target)
        assert result == "hello world"

    def test_accepts_string_path(self, tmp_path: Path) -> None:
        """Accepts a string path."""
        target = tmp_path / "input.txt"
        target.write_text("data")
        result = atomic_read(str(target))
        assert result == "data"

    def test_raises_for_missing_file(self, tmp_path: Path) -> None:
        """Raises OSError for missing file."""
        missing = tmp_path / "nonexistent.txt"
        with pytest.raises(OSError):
            atomic_read(missing)

    def test_inode_change_handled_gracefully(self, tmp_path: Path) -> None:
        """Handles OSError when re-checking stat (e.g., file replaced)."""
        target = tmp_path / "data.txt"
        target.write_text("content")

        # Patch stat to raise OSError on second call (simulating file replacement)
        call_count = [0]
        original_stat_method = Path.stat

        def patched_stat(self: Path, **kwargs: object) -> object:
            call_count[0] += 1
            if call_count[0] >= 2:  # noqa: PLR2004
                raise OSError("stat failed")
            return original_stat_method(self, **kwargs)

        with patch.object(Path, "stat", patched_stat):
            result = atomic_read(target)
        assert result == "content"

    def test_reads_multiline_content(self, tmp_path: Path) -> None:
        """Reads multiline file content."""
        target = tmp_path / "multi.txt"
        target.write_text("line1\nline2\nline3")
        result = atomic_read(target)
        assert "line1" in result
        assert "line2" in result
        assert "line3" in result

    def test_stat_differs_branch_is_silently_ignored(self, tmp_path: Path) -> None:
        """The 'if stat differs: pass' branch runs without error."""
        target = tmp_path / "data.txt"
        target.write_text("content")

        original_stat = target.stat()

        # Return a stat-like object with different inode on second call
        call_count = [0]
        original_stat_method = Path.stat

        class FakeStat:
            def __init__(self) -> None:
                self.st_ino = original_stat.st_ino + 999
                self.st_size = original_stat.st_size + 1

        def patched_stat(self_path: Path, **kwargs: object) -> object:
            call_count[0] += 1
            if call_count[0] >= 2:  # noqa: PLR2004
                return FakeStat()
            return original_stat_method(self_path, **kwargs)

        with patch.object(Path, "stat", patched_stat):
            result = _atomic_read(target)
        assert result == "content"


# ---------------------------------------------------------------------------
# Additional coverage: validate_url urlparse exception branch (line 278-280)
# ---------------------------------------------------------------------------


class TestValidateUrlExceptionBranch:
    """Tests for the urlparse exception branch in validate_url."""

    def test_urlparse_exception_raises_ssrf_error(self) -> None:
        """Raises SSRFError when urlparse itself raises."""
        with (
            patch.object(
                _security_impl,
                "urlparse",
                side_effect=Exception("bad url"),
            ),
            pytest.raises(_ImplSSRFError, match="Invalid URL"),
        ):
            _security_impl.validate_url("http://example.com")


# ---------------------------------------------------------------------------
# Additional coverage: atomic_write finally cleanup when replace fails (line 362)
# ---------------------------------------------------------------------------


class TestAtomicWriteFinally:
    """Tests for atomic_write finally block cleanup."""

    def test_temp_file_cleaned_up_when_replace_fails(self, tmp_path: Path) -> None:
        """Temp file is cleaned up even when replace raises."""
        target = tmp_path / "output.txt"

        with (
            patch("pathlib.Path.replace", side_effect=OSError("replace failed")),
            pytest.raises(OSError, match="replace failed"),
        ):
            _atomic_write(target, "data")

        # Temp file should be gone even though replace failed
        temp = target.with_suffix(".txt.tmp")
        assert not temp.exists()


@pytest.mark.parametrize("command", [
    "echo test > /dev/null",
    "echo test >> /etc/example",
    "echo test > /proc/example",
    "echo test > /sys/example",
    "cat < input.txt > output.txt",
    "echo test 2> errors.txt",
    "echo test > output.txt 2>&1",
    "cat 3<&0",
    "echo test &> output.txt",
    "echo test &>> output.txt",
])
@pytest.mark.parametrize("allowed_commands", [None, ["echo", "cat"]])
def test_redirects_survive_command_validation(
    command: str, allowed_commands: list[str] | None,
) -> None:
    """Redirections must not be rejected or mistaken for additional commands."""
    assert sanitize_command(command, allowed_commands) == command


@pytest.mark.parametrize("operator", [";", "&&", "||", "|", "&"])
def test_redirects_do_not_hide_disallowed_subcommands(operator: str) -> None:
    """Descriptor duplication must preserve checks on subsequent commands."""
    with pytest.raises(CommandInjectionError):
        sanitize_command(f"echo test 2>&1 {operator} denied", ["echo"])
