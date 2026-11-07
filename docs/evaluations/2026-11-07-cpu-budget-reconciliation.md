# Local CPU usage reconciliation — 2026-11-07

One local streamed request completed through public `Orchestrator.run_direct`,
reporting **27 input tokens and 2 output tokens**. Accounting settled all 29 tokens
and released its 53-token reservation. A second invocation and a fresh-process
invocation both stopped at the one-request limit before HTTP dispatch. The
[retained evidence](2026-11-07-cpu-budget-reconciliation.json) contains all three
outcomes, stable run/attempt identities and 18 passing consistency checks.

| Invocation | HTTP requests | Outcome | Accounting |
| --- | ---: | --- | --- |
| Initial turn | 1 | Responded in 12.097 seconds | 29 reported tokens settled; no hold |
| Same-process follow-up | 0 | `request_limit` | Same attempt and settled usage |
| Fresh-process follow-up | 0 | `request_limit` | Same attempt and settled usage |

The run used the existing `ornith1.5:9b` weights through an owned temporary Ollama
profile at `http://127.0.0.1:11434/v1`, with CPU-only inference, 14 threads, an
8,192-token context and temperature zero. The profile was created from the
installed model using Ollama's [create API](https://docs.ollama.com/api/create);
no weights were downloaded. Its exact manifest digests, effective parameters and
Ollama 0.40.7 version are retained. Ollama reported 6,326,572,808 bytes allocated
and zero GPU allocation after the request; this is not a peak-memory measurement.
The temporary profile was unloaded and deleted. The base model was unchanged.

The harness ran from clean source commit
`e28b79177eb8d4c46e6fccffe83b4f63c4539e25` on Python 3.12.13. It exposed no tools,
disabled compaction, capped output at eight tokens and requested streaming usage
with reasoning disabled. A transport guard allowed exactly one POST to the exact
local completion endpoint, with redirects and retries disabled. The SDK timeout
was 100 seconds and the outer turn deadline 110 seconds. Session and SQLite
accounting files lived in an isolated temporary directory. Harness digests and
dependency versions are retained; prompts, generated content and headers are not.

API spend was **USD 0**. All four configured token rates were explicitly zero,
dated 2026-11-07. Settled estimated cost is zero; provider billing remains unknown.
Grouped usage retains the exact configured price snapshot and reported counts
across restart. Unreported reasoning/cache-creation counts remain null with zero
request coverage. Neither denied follow-up reached the transport safety gate.

This qualifies successful local final-usage reconciliation and durable retention
for this one request. It supplements the earlier
[failed-request/unknown-hold probe](2026-11-07-local-budget-qualification.md), whose
outcome remains unchanged. It does not qualify coding quality, other providers,
multi-agent workloads, application memory on a 16-GB machine or the final release
artifact.
