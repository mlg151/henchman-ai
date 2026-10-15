# Provider usage evidence: headless team runtime

Read-only research, 2026-10-14. No usage aggregation is implemented by this note.

## Current evidence path

- `providers/base.py`: `StreamChunk.usage` is `dict[str, int] | None`, documented as prompt/completion/total tokens. There is no monetary cost, currency, provider request ID, or completeness schema.
- `providers/openai_compat.py:_extract_usage_from_chunk` copies only `prompt_tokens`, `completion_tokens`, and `total_tokens`. Other SDK usage fields, including provider-reported monetary cost if present, are discarded. `_process_stream_response` preserves usage-only trailing chunks. `_build_request_params` does not enable a usage streaming option by default; explicit request defaults can supply one. Confirm each provider's documented support before changing defaults across all compatible endpoints.
- OpenRouter, DeepSeek, and Ollama share the compatible adapter. `tests/providers/test_openrouter.py:test_chat_completion_stream_inherited` exercises extraction of the three token fields using real SDK chunk objects.
- `providers/anthropic.py:_AnthropicStreamProcessor` currently does not produce `StreamChunk.usage`. It ignores `message_start` and usage data on `message_delta`. Its rate limiter uses locally counted input/output tokens; these are not authoritative billing evidence.
- `core/agent_streaming.py:_accumulate_chunk` retains the latest usage snapshot, rather than summing snapshots. `generate_stream_events` consumes trailing chunks and emits one inner FINISHED carrying the latest snapshot. This is appropriate for cumulative snapshots and avoids counting the same request twice.
- `core/agent.py:_non_final_events` suppresses inner FINISHED. `_stream_with_stall_loop` can make several provider requests for internal stall retries but retains only the last `StreamState`. The outer FINISHED therefore exposes only the last retry's usage. Summing visible outer FINISHED events cannot recover all requests.
- `cli/headless.py:_forward_events` suppresses every provider FINISHED and emits one root terminal event later. It currently loses even the visible usage metadata.
- `utils/compaction.py` invokes `provider.chat_completion_stream` directly for summaries (near line 841). These requests bypass agent stream events. An aggregation limited to agent events must identify that scope and must not claim complete run billing.

## Existing components and reuse limits

- Keep `StreamChunk`, `StreamState`, `AgentEvent`, and stable `StreamContext.source_agent` as the transport path. Agent identity already attributes nested stream events to their role; headless JSON now preserves `source_agent`.
- `metrics/models.py:TokenUsageData` requires prompt/completion counts. `metrics/collector.py:record_token_usage` is sampled, recomputes total as prompt plus completion, and has no missing-data contract. `CostData` requires separate prompt/completion prices; those cannot be inferred from current stream evidence. This optional persistent telemetry collector is not an authoritative run accumulator.
- `api/endpoints/chat.py` also consumes FINISHED usage, defaults missing fields to zero, and accumulates metrics. Preserve legacy FINISHED payload compatibility if introducing an explicit usage event. Do not blindly reuse its missing-value behavior for reported evidence.
- `utils/tokens.py` token counting and Anthropic rate-limit accounting are estimates for runtime management, not billing data.

## Recommended minimal API

Introduce a small explicit usage event, such as `EventType.MODEL_USAGE`, once per actual provider stream attempt at the core streaming boundary. Suggested payload:

```python
{
    "scope": "agent_stream",
    "provider": provider_name,
    "model": configured_model,
    "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
    "coverage": "reported",  # or missing / partial
    "stream_complete": True,
}
```

Use `source_agent` on the event rather than parsing role names from text. Distinguish configured model metadata from a provider-reported actual model if routing can select a different one. A request identifier is useful if the adapter exposes a real one; do not fabricate provider IDs.

Emit after the stream has consumed trailing usage, before its FINISHED event. On a recoverable provider error, emit a partial/missing usage snapshot **before ERROR**: `ExecutionController` stops consuming after ERROR. Do not yield from cancellation cleanup/finally. Cancellation without a terminal summary must never be presented as complete coverage; durable accounting of cancelled attempts would require a separate non-yielding observer mechanism.

Keep legacy FINISHED usage for compatibility, but aggregate only MODEL_USAGE events. This avoids adding both inner attempt usage and outer finish usage. Internal stall retries now pass through `_non_final_events` as separate observable attempts. Root, specialist, and delegation retry attempts all count; repeated equal snapshots from different requests are not duplicates.

Implement a small in-memory accumulator with total and per-role counters, bounded by the agent catalog rather than retained event history. Track:

- observed attempt count;
- attempts with valid reported usage, missing usage, and incomplete streams;
- sums and reported-count coverage for each known field;
- explicit scope `agent_streams`, excluding uninstrumented compaction requests;
- monetary cost `null`/unavailable until adapters preserve actual reported cost and currency.

Validate exact nonnegative integers (excluding booleans) for token fields. Do not silently convert malformed values or missing fields to evidence of zero. Preserve reported `total_tokens`; do not assume it can always be reconstructed from the other two fields. For optional billing data, validate finite nonnegative values and currency, retain its provenance, and do not sum different currencies. Avoid pricing tables or inferred estimates in this milestone.

## Focused verification plan

Reuse nearby fixtures and add tests at each boundary:

1. `tests/providers/test_openrouter.py` and `tests/providers/test_openai_compat.py`: trailing usage-only chunk, cumulative repeated usage snapshots, absent usage, partial/malformed fields, and supported explicit request options. If extending billing extraction, test provider-reported monetary fields independently from tokens.
2. `tests/providers/test_anthropic.py`: real SDK message-start input and message-delta output usage, cache fields if supported, no summing of cumulative output snapshots. Keep rate-limit estimates separate.
3. `tests/core/test_agent_streaming.py`: exactly one usage event per provider attempt, after trailing usage and before FINISHED; reported zero counts; missing/partial usage; partial usage before ERROR; cancellation closes resources without yielding from finally.
4. `tests/core/test_agent_stall_lifecycle.py`: two internal provider attempts expose two usage events while preserving the existing single outer FINISHED contract. Outer FINISHED must not cause duplicate aggregation.
5. `tests/cli/test_headless_orchestration.py`: root plus specialist plus continuation totals and per-role attribution; delegated retries; same role repeated attempts; missing child usage marks coverage incomplete; one terminal FINISHED containing the summary; error path preserves observed totals as partial evidence.
6. Tests for compaction must either verify its explicit exclusion from scope or instrument its provider request before permitting whole-run completeness claims.

Do not ship a FINISHED-only sum labeled total run cost: it would omit internal stalls, all current Anthropic usage, and summarization requests.
