# Missing Contract: Ops RateLimiter and MigrationRunner Interfaces

**Severity:** Low  
**Location:** `src/henchman/ops/rate_limits.py`, `src/henchman/ops/migrations.py`

## The gap

### RateLimiter

`src/henchman/ops/rate_limits.py` defines `RateLimiter` with `allow()` method.
`parse_rate_limit()` parses limit strings like `"1000/hour"` into `ParsedRateLimit`.
**No contract test** validates the parsing or rate-limiting behavior.

### MigrationRunner

`src/henchman/ops/migrations.py` defines `MigrationRunner` with `current_version()`
and `migrate()` methods. **No contract test** validates the migration lifecycle:
- Applying migrations in order
- Tracking schema version
- Idempotency of re-application

## What's consumed

- `RateLimiter` is consumed by `api/endpoints/` and `api/server.py` for API
  request rate-limiting.
- `MigrationRunner` is consumed by `ops/state.py` and `cli/startup` initialization.

## Recommended contract test

For RateLimiter:

```python
def test_parse_rate_limit_contract():
    """parse_rate_limit() must handle standard formats."""
    limit = parse_rate_limit("1000/hour")
    assert limit.limit == 1000
    assert limit.window_seconds == 3600

    limit = parse_rate_limit("10/minute")
    assert limit.limit == 10
    assert limit.window_seconds == 60

    limit = parse_rate_limit("5/second")
    assert limit.limit == 5
    assert limit.window_seconds == 1
```

For MigrationRunner:

```python
def test_migration_runner_contract(ops_store):
    """MigrationRunner must apply migrations in order."""
    calls = []
    m1 = Migration(version=1, migrate=lambda: calls.append("m1"))
    m2 = Migration(version=2, migrate=lambda: calls.append("m2"))
    state_store = AppStateStore(ops_store)

    runner = MigrationRunner(ops_store, "test", [m1, m2])
    assert runner.current_version() == 0

    results = runner.migrate(state_store)
    assert results == ["Applied migration 1", "Applied migration 2"]
    assert runner.current_version() == 2

    # Re-apply should be no-op
    results = runner.migrate(state_store)
    assert results == []
```

## Priority

Low — these are internal interfaces with stable semantics. The risk of
regression is low relative to user-facing boundaries.
