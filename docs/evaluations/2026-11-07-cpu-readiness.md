# CPU model readiness and coding checks — 2026-11-07

The installed `ornith1.5:9b` model answered a bounded readiness prompt and produced
a valid `read_file` call. Four subsequent coding attempts failed, followed by
**one independently verified syntax-repair diagnostic**.
These observations are separate from the
[27B GPU-server timeout cohort](2026-11-07-local-baseline.md); no failed run has
been replaced or removed from its denominator.

| Cohort | Planned / recorded | Outcomes | Verified successes |
| --- | --- | --- | --- |
| [8K syntax repair](2026-11-07-cpu-syntax-8k.json) | 2 / 2 | Two context-capacity errors | 0 |
| [16K syntax repair](2026-11-07-cpu-syntax-16k.json) | 2 / 2 | One timeout; one tool-round limit | 0 |
| [16K diagnostic](2026-11-07-cpu-syntax-diagnostic.json) | 1 / 1 | Passed independent syntax/behavior checks | 1 |

The first two cohorts used the existing `syntax-fix` scenario and its independent oracle,
the canonical engineer prompt and role-scoped production tools, a 300-second turn
limit and six tool rounds. API spend was zero; token usage was unavailable in
these failed runtime results. The test workspaces were removed by the harness.

## Readiness and profile configuration

An initial native Ollama request with `num_gpu=0` returned `OK` in 22.36 seconds,
including 21.53 seconds of model load. A separate native tool-call probe returned
`read_file({"path":"example.py"})` in 11.32 seconds. An OpenAI-compatible API
probe against the isolated test profile returned the same valid call in 22.42
seconds. These tiny probes establish basic response and function-call support;
they are not application latency benchmarks or successful coding tasks.

The temporary model alias `henchman-eval-cpu-ornith15-20261107` was created from
the already-installed `ornith1.5:9b` without downloading or modifying its base
weights. Its parameters were `num_gpu=0`, `num_thread=14`, `temperature=0`, and
initially `num_ctx=8192`. The compatible provider used the loopback endpoint
`http://127.0.0.1:11434/v1`, `reasoning_effort="none"`, a 512-token response cap,
and `stream_options={"include_usage": true}`. No paid service was called.

The 8K cohort retained the default engineer configuration. The server rejected
both requests because they needed 8,810 tokens and only 8,192 were available.
Its [effective profile records](2026-11-07-cpu-syntax-8k-profiles.json) show that
the agent had no explicit `context_window`; that configuration did not provide
a valid capacity match for this server.

For the separate 16K cohort, the temporary alias was configured with
`num_ctx=16384`, and the agent used
`AgentConfig(max_tokens=13926, context_window=16384)`. Its
[profile records](2026-11-07-cpu-syntax-16k-profiles.json) retain tool names,
prompt hash and effective limits. The first attempt timed out after approximately
301 seconds including cleanup; the second reached the six-round limit after
approximately 97.93 seconds. Neither was marked task-verified.

The [provenance record](2026-11-07-cpu-syntax-16k-provenance.json) captures source
commit `6b99036`, evaluator Python 3.11.15, Ollama 0.40.7, model manifest digests,
provider options and observed allocation. Ollama reported zero GPU memory and
about 6.49 GB of model allocation at 16K context. Allocation is not measured peak
process memory; this host has approximately 128 GB of system RAM and does not
establish behavior on an actual 16-GB machine. The native Windows/macOS, long-task,
quality, memory and responsiveness gates in #28 remain open.

## Diagnostic result and cleanup

A separate single attempt with a ten-round ceiling and the same 300-second turn
bound passed, with a recorded runtime duration of 117.74 seconds. Its
[redacted tool trace and delivered source](2026-11-07-cpu-syntax-diagnostic-details.json)
show successful `read_file`, `edit_file`, `python_exec` and `task_output` calls.
The independent oracle confirmed the expected greeting and return value. The
report includes a usage observation of 9,366 input and 180 output tokens; this is
not asserted to be a complete aggregate across all provider requests.

This attempt used four tools, so the observations do not establish that increasing
the round ceiling caused the success. The earlier capped attempt had no retained
tool trace and remains recorded as a failure. The differing configurations and
tiny sample do not support a general success-rate or comparative-performance claim.

After the diagnostic, the temporary profile was unloaded and deleted. The base
`ornith1.5:9b` model remained installed, and the GPU servers remained running.
Broader CPU task qualification and the remaining #13/#28/#30 release gates remain
required; one successful diagnostic does not satisfy them.
