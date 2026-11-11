# Revised CPU corpus readiness — 2026-11-07

The separate revised readiness run passed both protocol probes and the canonical
syntax-repair oracle. The [original failed attempt](2026-11-07-cpu-corpus-readiness.md)
remains unchanged. This diagnostic allowed a 600-second HTTP read/write timeout
inside the existing 600-second whole-case deadline; protocol probes retained
their individual 120-second limits. The twelve-case corpus is a subsequent run,
not part of these results.

| Stage | Requests | Outcome | Time including cleanup |
| --- | ---: | --- | ---: |
| Exact response and structured file read | 2 | Both passed | 34.33 seconds before final client close |
| Canonical syntax repair | 7 | Independent oracle passed | 347.65 seconds |

The first coding response headers arrived after 212.54 seconds, exceeding the
earlier diagnostic's 120-second request limit. Subsequent header waits ranged
from 1.90 to 11.62 seconds. These client-side observations do not isolate model
prefill from other server work or establish a general latency improvement.

All nine requests retained final server-reported usage. Syntax repair reported
64,244 input and 572 output tokens across its seven requests; the two protocol
probes reported 536 input and 77 output tokens. These are request-level sums.
The baseline runner's separate final-turn observation of 9,530 input and 150
output tokens is retained with its narrower scope. API spend was USD 0.

The [evidence record](2026-11-07-cpu-corpus-readiness-v2.json) binds clean source
commit `add457cd2e6ae1b4debab303bf80d20ce1af5d9f`, the installed model digest,
effective CPU parameters, harness hashes, per-request timeouts, usage and raw
artifact hashes. Model, canonical prompts, tools, oracle and case limits match
the previous diagnostic. The revised harness also handles an empty successful
delete acknowledgement and distinguishes normal SDK closure after SSE `[DONE]`
from an interrupted response. Those corrections did not rewrite earlier receipts.

Owned runtime work and provider clients were joined, the workspace was archived
and removed, and the temporary model alias was unloaded and deleted. The base
model digest remained unchanged. No provider/tool guard violation or cleanup
failure was recorded.

Late process-tree samples include the model runner and owned Python worker, but
they began after the case started and cannot establish whole-run peak memory.
Some process proportional-memory counters were unavailable due to permissions.
The host still has approximately 128 GB RAM; this is not a 16 GB machine result.
The wider corpus, repeated-run reliability, native setup and hardware gates
remain open. A single successful diagnostic does not qualify an included model.
