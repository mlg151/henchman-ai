# Missing Contract: Ops Observability Service Payloads

**Severity:** High  
**Location:** `src/henchman/ops/observability.py`  
**Source types:** `AnalyticsService`, `TelemetryService`, `CostTrackingService`, `DiagnosticTrackingService`

## The gap

`src/henchman/ops/observability.py` defines four services that produce structured
dictionary payloads stored in the ops store and potentially exposed to external
consumers (API endpoints, analytics pipelines). **None of these payload shapes
have JSON Schema contracts or contract tests.**

### AnalyticsService.record()

Returns a dict with keys like `id`, `event_type`, `payload`, `timestamp`, `source`.

### TelemetryService.record()

Returns a dict with keys like `id`, `event_type`, `tokens`, `tool_calls`, `payload`, `timestamp`.

### CostTrackingService.record_usage()

Returns a float cost value (not a dict — this one is OK as a simple type).

### CostTrackingService.summary()

Returns a dict with keys like `total_cost`, `total_tokens`, `events_by_model`.

### DiagnosticTrackingService.record()

Returns a dict with keys like `id`, `event_type`, `status`, `details`, `timestamp`.

## What's consumed

These service records are consumed by:
- `ops/store.py` for persistence
- Potential API metrics endpoints (not yet built)
- External analytics pipeline integrations
- The `ops/sync.py` settings sync module

## Recommended contract schemas

Create four new schema files:

| Schema | Path |
|--------|------|
| `analytics_event` | `tests/contracts/schemas/ops/analytics_event.json` |
| `telemetry_event` | `tests/contracts/schemas/ops/telemetry_event.json` |
| `cost_summary` | `tests/contracts/schemas/ops/cost_summary.json` |
| `diagnostic_event` | `tests/contracts/schemas/ops/diagnostic_event.json` |

## Recommended contract test

Add to a new or existing ops contract test:

```python
def test_observability_payloads_match_contracts(contract_suite, ops_store):
    analytics = AnalyticsService(ops_store)
    record = analytics.record("app_start", {"version": "1.0.0"})
    assert_contract_matches(
        payload=record,
        schema_name="ops/analytics_event",
        contract_suite=contract_suite,
    )
```

## Cross-boundary impact

The `Observability` services' return shapes are part of the **ops subsystem's
public API**. Although not yet exposed via HTTP endpoints, the ops store is
a persistence boundary — stored shapes should be schema-protected.
