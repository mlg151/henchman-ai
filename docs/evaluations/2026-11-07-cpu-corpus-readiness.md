# CPU corpus readiness — 2026-11-07

Readiness failed before the twelve-case corpus could start. The local model
passed the exact-response and structured `read_file` checks, then its first
canonical syntax-repair request timed out without returning HTTP headers or
response bytes. No model-request retry or replacement success is included in
this cohort. [Recorded evidence](2026-11-07-cpu-corpus-readiness.json) preserves
the outcome, bounds, request hashes, usage availability and cleanup verification.

| Stage | Requests | Outcome |
| --- | ---: | --- |
| Exact `OK` and structured file read | 2 | Both passed; 32.48 seconds combined |
| Canonical `syntax-fix` | 1 | Pre-response timeout; 122.41 seconds including cleanup |
| Frozen twelve-case corpus | 0 | Withheld after failed readiness |

The first two requests reported 536 input and 77 output tokens in total. Usage
for the timed-out request remains unknown. Local API spend was USD 0; hardware
and electricity costs were not estimated. The syntax workspace retained its
original source, no tools ran, and owned workspace cleanup completed.

The run used clean commit `add457cd2e6ae1b4debab303bf80d20ce1af5d9f`, Python
3.12.13, and an isolated CPU-only alias of the installed `ornith1.5:9b` model.
Effective parameters were 16,384 context tokens, 14 CPU threads, no GPU allocation
and temperature zero. Requests capped output at 512 tokens, disabled reasoning
and SDK retries, and allowed only the exact local compatible completion endpoint.
Canonical prompts, tools and independent oracles were unchanged; the engineer
input budget was 13,926 tokens with automatic compaction disabled.

The whole coding case allowed 600 seconds and twelve requests, but the harness's
HTTP read timeout was 120 seconds. The first syntax request contained 37,930
bytes, 31 tool declarations and approximately 16,405 message characters. A longer
prefill than the tiny protocol checks is plausible; no server timing measurement
establishes the cause. This observation establishes a pre-response timeout, not
an observed incorrect model repair. A revised diagnostic must remain a separate
cohort with its changed HTTP allowance disclosed.

Cleanup unloaded the owned alias and received HTTP 200 from its deletion. The
harness incorrectly expected JSON in the empty successful deletion response and
recorded a cleanup parsing failure. Subsequent read-only model-list and residency
checks confirmed that the alias was absent and unloaded, the base digest was
unchanged and no model remained resident. The original failure receipt was
preserved, with this verification added separately.

Successful protocol receipts also retain an original bookkeeping inconsistency:
the SDK stopped consuming after the SSE `[DONE]` marker, so final usage is present
while `stream_complete` is false and closure is labeled `GeneratorExit`. The
saved raw stream and hash remain available; the original receipts were not
rewritten.

The host reports 132,210,106,368 bytes of physical memory. Samples select processes
named `ollama` and do not establish coverage of its model-runner children or peak
whole-application memory. This is not qualification on a 16 GB laptop. The
provider gate and scrubbed environment also do not universally sandbox arbitrary
subprocess networking. The earlier [CPU experiments](2026-11-07-cpu-readiness.md)
remain separate; #13/#28 quality, repeated-run and hardware gates are still open.
