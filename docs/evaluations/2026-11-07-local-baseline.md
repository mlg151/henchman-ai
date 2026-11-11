# Local development baseline — 2026-11-07

The [unaltered runner report](2026-11-07-local-baseline.json) records **22 timeouts
out of 22 planned attempts, with no verified successes**. Each of the eleven
registered scenarios ran twice with a 120-second turn limit and ten tool rounds.
The runner exited 1. This result does not qualify model task performance or the
v0.4.2 release.

| Observation | Recorded value |
| --- | --- |
| Completed attempt records | 22 / 22 |
| Verified successes | 0 / 22 |
| Timeouts | 22 / 22 |
| Attempt-duration p50 | 120.068 seconds |
| Attempt-duration p95 | 120.412 seconds |
| Token usage | Unavailable; not reported as zero |
| API cost | $0; local server, no hosted calls |
| Report generated | 2026-11-07 13:58:53 UTC |

These latency values measure bounded attempts, including timeout cleanup; they
are not successful task-completion or token-generation latency. No failed attempt
was omitted or retried into the same denominator.

## Invocation and provenance

The command ran from the development checkout:

```bash
EVAL_PROVIDER=openai_compat \
EVAL_MODEL=qwen38-27b-iq3s \
EVAL_BASE_URL=http://127.0.0.1:8081/v1 \
uv run --extra dev python -m evals.baseline_runs \
  --runs 2 --timeout 120 --max-iterations 10 \
  --report /tmp/henchman-v042-local-baseline.json
```

The checkout was on `b18adb0` at invocation, with session-persistence work in
progress. Implementation and offline tests continued during the evaluation.
The evaluator, helpers and corpus source did not change between `b18adb0` and
`054584f`; this does not establish an exact clean release-artifact identity.
The model binary was not hashed at invocation. These are development observations,
not final-build, isolated-load or reproducible model-identity qualification.

The report's `requested.model` is `null` because the runner read the `model`
attribute while this provider exposes `default_model`. The invocation above
records the requested alias separately; the report is preserved without editing
its historical fields. The runner now reads `default_model` with a `model`
fallback, covered by an offline regression.

Read-only process inspection after the run found two llama.cpp servers using
`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf`, alias `qwen38-27b-iq3s`, 131072 context,
one parallel slot each, 99 GPU layers and a 2048 reasoning budget. The host has
two NVIDIA CMP 100-210 GPUs with 16 GiB each and two Intel Xeon Gold 6132 CPUs.
This GPU-backed host does not satisfy the proposed CPU-only/16-GB profile in #28.

## Follow-up diagnosis and remaining gates

Immediately after the cohort, a health request to port 8081 returned `ok`, but
a slots request exceeded its three-second read timeout. Independent direct
eight-output-token requests to ports 8081 and 8082 both exceeded 30 seconds.
Both GPUs were busy at the observation point. These checks show that basic health
did not establish inference readiness; they do not identify whether contention,
queued work, model settings or another cause explains the timeouts. Existing
servers were left running.

Before another full cohort, establish bounded direct inference and tool-call
readiness on an available local or explicitly free hosted endpoint, record model
identity and effective profile metadata, then run declared bounds without replacing
this result. Successful local qualification, the twelfth corpus scenario, hosted
comparison under the zero-spend constraint, and exact final-artifact qualification
remain open in #13, #28 and #30. No paid model test is authorized by this report.
