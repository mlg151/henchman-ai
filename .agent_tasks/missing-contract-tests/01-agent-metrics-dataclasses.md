# [COMPLETED] Missing Contract: Agent Metrics Dataclasses

**Severity:** Medium — resolved
**Location:** `src/henchman/agents/metrics.py`
**Source modules:** `PerformanceMetrics`, `QualityMetrics`, `ToolMetrics`, `OrchestratorMetrics`

## The gap

`src/henchman/agents/metrics.py` defines four dataclass-based metrics containers
that are serialized to dicts and consumed across multiple subsystems (orchestrator
loop, delegation runner, metrics reporter). **None of these classes have a JSON
Schema contract or a contract test** verifying their serialized shape.

The `OrchestratorMetrics` class in particular supports both attribute access and
dict-like `__getitem__`/`__setitem__` access, which means its shape is a key
contractual surface. Any change to field names or structure silently breaks
consumers in `metrics_reporter.py`, `delegation.py`, `cli/output_handler.py`, etc.

## What's consumed

- `metrics_reporter.py` reads `OrchestratorMetrics` fields like `performance`,
  `quality`, `tools`, `delegation_count`, `total_tool_calls`, etc.
- `cli/output_handler.py` reads status values from the metrics.
- `delegation.py` tracks metrics per delegation run.

## Resolution (completed 2025-07-18)

### New JSON Schema contracts

| Schema file | Covers | Key fields |
|---|---|---|
| `tests/contracts/schemas/metrics/performance_metrics.json` | PerformanceMetrics | task_start_time, task_end_time, task_duration_minutes, files_accessed, tool_usage_by_type, delegation_rate, file_re_reads, error_rate, context_window_usage |
| `tests/contracts/schemas/metrics/quality_metrics.json` | QualityMetrics | test_results (passing/total/percentage), code_coverage, linting_status (errors/warnings), documentation_coverage |
| `tests/contracts/schemas/metrics/tool_metrics.json` | ToolMetrics | total_tool_calls, successful_tool_calls, failed_tool_calls, 6 category-specific call counters |
| `tests/contracts/schemas/metrics/orchestrator_metrics.json` | OrchestratorMetrics | Top-level fields + inlined performance/quality/tools sub-objects |

### What was tested

**18 contract tests** in `tests/contracts/test_metrics_contracts.py` across 4 test classes:

- `TestPerformanceMetricsContract`: default, populated, reset
- `TestQualityMetricsContract`: default, populated, reset
- `TestToolMetricsContract`: default, with calls, reset, error_rate preservation
- `TestOrchestratorMetricsContract`: default, populated, reset_for_run, __getitem__/__setitem__ round-trip, get() fallback, update_tool_metrics

### Key design decisions

- **init=False constants filtered**: PerformanceMetrics has ALL-CAPS constants (DELEGATION_RATE_TARGET, etc.) that leak through `asdict()`. The helper `_performance_metrics_to_dict()` filters them since they're class-level implementation details, not instance metrics data.
- **No $ref used**: ContractSuite validator doesn't support $ref resolution; sub-schemas are inlined in orchestrator_metrics.json.
- **No production code changes**: Serialization helpers live in the test file.

## Cross-boundary impact

The `OrchestratorMetrics` shape is a **cross-subsystem contract** — it flows
from `agents/metrics.py` → `agents/metrics_reporter.py` → `cli/output_handler.py`.
Any structural change now triggers contract test failures.
