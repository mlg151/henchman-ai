# Missing Contract: Tool Security Boundary (sanitization contracts)

**Severity:** Medium  
**Location:** `src/henchman/tools/security.py`

## The gap

`src/henchman/tools/security.py` defines a security boundary for tool inputs
with functions like `sanitize_command()`, `validate_path()`, `validate_url()`,
and `sanitize_error_message()`. **There is no contract test** for the security
guarantees of these functions.

This is a *behavioral contract* rather than a shape contract:

- `sanitize_command(command)` must reject shell metacharacters
- `validate_path(path)` must reject path-traversal attempts
- `validate_url(url)` must reject SSRF vectors (private IPs, etc.)

## What's consumed

These functions are called by:
- `tools/builtins/shell.py` — command execution
- `tools/builtins/file_read.py` and `file_write.py` — file operations
- `tools/builtins/web_fetch.py` and `web_search.py` — URL validation

## Recommended contract test

Add a security-focused contract test:

```python
def test_sanitize_command_rejects_injection():
    """Shell command sanitization must block known injection patterns."""
    assert sanitize_command("ls -la") == "ls -la"
    with pytest.raises(CommandInjectionError):
        sanitize_command("ls; rm -rf /")
    with pytest.raises(CommandInjectionError):
        sanitize_command("ls | cat /etc/passwd")


def test_validate_path_rejects_traversal():
    """Path validation must block traversal attempts."""
    assert validate_path("/tmp/test.txt") == Path("/tmp/test.txt")
    with pytest.raises(PathTraversalError):
        validate_path("../../../etc/passwd")
    with pytest.raises(PathTraversalError):
        validate_path("/etc/passwd")


def test_validate_url_rejects_ssrf():
    """URL validation must block private-network targets."""
    assert validate_url("https://example.com") == "https://example.com"
    with pytest.raises(SSRFError):
        validate_url("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(SSRFError):
        validate_url("http://10.0.0.1/admin")
```

## Existing test coverage

There are tests in `tests/tools/` for security, but they are unit tests for
individual tools rather than contract-level security guarantees.

## Priority

Medium — a regression in security sanitization would be a serious issue.
