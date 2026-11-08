# Local live baseline on port 8082 — 2026-11-07

The [unaltered runner report](2026-11-07-local-baseline-8082.json) records a
**live** zero-spend cohort against the locally running llama.cpp endpoint on
port 8082 (GPU 1): **13 verified successes, 10 timeouts and 1 verification
failure out of 24 planned attempts** (12 cases × 2 runs, 120-second turn
limit, 10 tool rounds). The runner exited 1 because not every attempt was a
success; the exit code does not invalidate the report. Each recorded attempt
remains in the denominator; none was omitted or retried into it.

| Observation | Recorded value |
| --- | --- |
| Completed attempt records | 24 / 24 |
| Verified successes | 13 / 24 |
| Timeouts (120 s wall-clock budget) | 10 / 24 |
| Verification failures | 1 / 24 (`tool-failure-recovery` run 2) |
| Runtime errors | 0 / 24 |
| Attempt-duration min / p50 / p95 / max | 46.3 s / 97.5 s / 120.0 s / 120.0 s |
| Sum of successful-record token observations | 122,832 in / 2,674 out; incomplete scope |
| API cost | $0; local server, no hosted calls |
| Report generated | 2026-11-08 00:22:44 UTC |

The runner's token fields retain final scenario/turn observations, not complete
request-level aggregates across every tool round or delegated call. These sums
must not be treated as full-cohort consumption; timed-out usage remains unknown.

Per-case outcomes (successes / 2):

| Case | Outcome |
| --- | --- |
| add-method-class | 1 (1 timeout) |
| counter-refactor | 2 |
| fibonacci | 1 (1 timeout) |
| interruption-recovery | 2 |
| multi-file-edit | 2 |
| package-lifecycle | 0 (2 timeouts) |
| python-reuse | 0 (2 timeouts) |
| rename-variable | 2 |
| semantic-bug-fix | 0 (2 timeouts) |
| syntax-fix | 2 |
| test-docs | 0 (2 timeouts) |
| tool-failure-recovery | 1 (1 verification failure) |

## Distinction from the preserved 2026-11-07 cohort

This report is a **different live observation** from
[2026-11-07-local-baseline.md](2026-11-07-local-baseline.md) (22 timeouts /
22, port 8081, corpus of 11 scenarios before the twelfth case was frozen).
That report is preserved unaltered and is not superseded: the denominators
differ (11 vs 12 cases), the endpoints differ (8081 vs 8082), and the load
conditions differ (both GPUs busy at 98 % versus GPU 1 idle at 0 %). This
cohort is also a **live inference run**, explicitly distinct from offline
replay and scripted checks: every attempt was a bounded execution against the
running model with real token generation and tool calls.

## Invocation and provenance

The command ran from the development checkout:

```bash
EVAL_PROVIDER=openai_compat \
EVAL_MODEL=qwen38-27b-iq3s \
EVAL_BASE_URL=http://127.0.0.1:8082/v1 \
uv run --extra dev python -m evals.baseline_runs \
  --runs 2 --timeout 120 --max-iterations 10 \
  --report /tmp/henchman-v042-local-baseline-8082.json
```

The checkout was on `5b97b01` at invocation, with another session's
uncommitted modifications in `src/henchman/advanced/*`, `src/henchman/agents/*`
and `src/henchman/cli/textual_app.py` present in the working tree (recorded
for provenance; the frozen evaluator, helpers and corpus were committed at
that HEAD). This is a development observation, not final-build, isolated-load
or reproducible model-identity qualification.

The report's `requested.model` is `qwen38-27b-iq3s` — the runner now reads
`default_model` with a `model` fallback, fixing the `null` recorded by the
earlier cohort.

## Readiness gate (satisfied before this cohort)

Before launching, both readiness probes against `http://127.0.0.1:8082/v1`
passed while GPU 1 sat at 0 % utilization (raw evidence in `/tmp/opencode/`):

- Bounded direct inference: 16 tokens in 23.6 s, HTTP 200 (visible content
  empty — the 2048-token reasoning budget consumed the small cap;
  `finish_reason: length`).
- Tool-call readiness: proper structured `tool_calls` with
  `finish_reason: tool_calls` in 5.45 s, HTTP 200.

Model identity/profile: alias `qwen38-27b-iq3s`
(`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf`, GGUF, 131072 context, 99 GPU layers,
2048 reasoning budget), `system_fingerprint: b1-6cb3e67`. The model is a
thinking model. Reasoning and generation may contribute to latency, but this
report does not isolate their durations or establish the cause of each timeout.
Every timeout remains a failed attempt in the fixed cohort denominator.

## Cost and spend provenance

No hosted calls were made and no paid model was used. The runner classified
the provider as a `local` cohort with `cost.amount_usd: 0.0`,
`billing: none`, `source: local`. No `OPENROUTER_API_KEY` was present in the
environment; the OpenRouter free-tier hosted cohort remains pending.

## Remaining gates

Hosted free-tier comparison under the zero-spend constraint, exact
final-artifact qualification, and the UI baseline (#32) remain open in #13,
#30 and #32. No release-readiness claim is made by this report.
