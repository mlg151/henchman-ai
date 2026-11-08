# CPU readiness v6: no-go — 2026-11-08 UTC

**Neither tested profile qualifies as an included local model.** Both passed the
exact-response and structured-file-read protocol probes, then reached the
unchanged ten-tool-round limit during syntax repair. The readiness gate refused
both candidates. All **24 planned corpus attempts remained `not_run`**: six cases,
twice each, for each of two models. This is not a 0/24 model-success score, and
protocol success is not coding acceptance.

The [bounded evidence record](2026-11-08-cpu-readiness-v6.json) preserves those
separate denominators, all dispatched-request counts, exact artifact identities,
limits, missing memory observations and cleanup results. This audit read existing
artifacts only. It made no inference or management requests, reran no scenario or
oracle, and changed no harness or earlier evidence.

## Observed results

| Model | Readiness stage | Outcome | Requests | Seconds including worker supervision/cleanup | Reported input/output tokens |
| --- | --- | --- | ---: | ---: | ---: |
| ornith1.5:9b | Two protocol probes | Both passed | 2 | 44.24 | 544 / 85 |
| ornith1.5:9b | Syntax repair | Ten-tool-round limit; not accepted | 11 | 346.12 | 105,569 / 721 |
| Spark-X2.6:4b | Two protocol probes | Both passed | 2 | 41.86 | 360 / 66 |
| Spark-X2.6:4b | Syntax repair | Ten-tool-round limit; not accepted | 11 | 276.00 | 95,491 / 567 |

Both syntax records retain `outcome=runtime_error`, `task_verified=false` and
`Tool iteration limit (10) reached`. Each logged eleven tool requests; the final
request received the iteration-limit failure. Model prose, earlier successful
tools and archived candidate files do not substitute for an accepted independent
oracle result. No later result was substituted, and neither failure was retried.

The retained traces identify concrete recovery problems to investigate offline:
Ornith encountered string-match, mixed edit-mode and formatting failures before
rewriting the file; Spark made repeated task-output requests with an unresolved
task identifier. Both consumed the available rounds before completion. These
observations do not by themselves establish whether a model, prompt or runtime
change would resolve the failures.

The planned cases were `multi-file-edit`, `python-reuse`, `semantic-bug-fix`,
`package-lifecycle`, `tool-failure-recovery` and `interruption-recovery`. None ran
in this cohort. There is no repeated-run reliability or comparative latency claim.
The first syntax response headers arrived after 162.47 seconds for Ornith and
103.16 seconds for Spark. These client observations include possible loading,
prefill and server work; they do not isolate generation latency.

## Frozen inputs and isolation

Execution used source commit
[`6ee824bc36ffeaf51fce40fd025155fdd0faa178`](https://github.com/mlg151/henchman-ai/commit/6ee824bc36ffeaf51fce40fd025155fdd0faa178),
which was a development snapshot under release review, not a fully qualified
release or installed-wheel result. The private runtime was Ollama **0.40.7**.
Exact source model identities were:

| Model | Format | Source manifest SHA256 |
| --- | --- | --- |
| ornith1.5:9b | GGUF, 9.0B, Q4_K_M | `fde90266e6077dc19610515813b0065eae248ea2d5ac8064f52e11ca3f5bef3c` |
| Spark-X2.6:4b | GGUF, 4.1B, BF16 | `c39c7bb372bda48de1e4d264bc079ebba3952a2749cd59797c68cd48b4696d27` |

Spark's alias manifest was a **digest-matched reconstruction**, not a discovered
on-disk alias. Earlier read-only local API observations supplied the exact alias
digest. A finite reconstruction using the existing parent manifest and existing
19-byte parameters blob matched it byte-for-byte. The parent digest
`44ca4d700630e9a402cb439007132da135b2ca5329985b7f8944d04b7d59f43a`
was not substituted for the requested alias. The original reconstruction record
and its hash are retained in the JSON.

Each candidate used independent private model-file copies on the main disk and
an owned loopback server/process group. The audit rehashed all seven copied blob
instances and checked that their inodes differed from the corresponding original
files. Integrity copying warms the OS page cache; no physically cold-storage
claim follows. Existing user servers and occupied GPUs were outside this cohort's
ownership.

Both profiles enforced `num_ctx=16384`, `num_gpu=0`, `num_thread=14` and
`temperature=0`. Observed residency reported zero VRAM and a 16,384-token context
for both candidates. Syntax used the canonical engineer profile with a
13,926-token input budget and automatic compaction disabled. Requests capped
output at 512 tokens; SDK and tool retries were zero. The syntax readiness cap was
12 requests; each planned corpus case allowed 24 requests and 600 seconds.
Protocol probes each had a 120-second deadline. Provider traffic was restricted
to the owned endpoint; these controls are not a universal network sandbox for
arbitrary tool subprocesses.

## Receipts, memory and cleanup

All **26 dispatched requests** have final server-reported usage and retained SSE
`[DONE]`: **201,964 input and 1,439 output tokens**. Every request/response hash
matched its final receipt, with no raw-byte omissions. All dispatches settled and
all stream closes joined. The SDK stopped at `[DONE]` before transport EOF on all
26 responses; this is recorded separately and is not an incomplete-usage claim.
The launcher's overall `usage_complete=false` remains preserved: that flag
requires all 24 corpus attempts, which did not run. Final-turn baseline token
fields remain separate from the request-level sums.

Local API spend was **USD 0**, with no hosted calls. Hardware and electricity
costs were not estimated.

The host reported **132,210,106,368 bytes (123.13 GiB)** of physical RAM. It was
not the named 16 GB CPU laptop required by [#28](https://github.com/mlg151/henchman-ai/issues/28).
The sampler retained **1,536 observations**, of which **10 had missing process
reads** during process exits; 1,526 had complete same-sample totals. The requested
interval was 0.25 seconds; observed gaps ranged from 0.284 to 0.927 seconds.

The maximum complete sampled total was **11,093,028,864 bytes PSS (10.331 GiB)**
and **11,143,000,064 bytes RSS (10.378 GiB)**. At the PSS peak, coverage included
the launcher, Ollama server, actual `llama-server` runner and Python syntax worker.
This sampled PSS already exceeds the proposed 10 GiB limit. RSS double-counts
shared pages; PSS apportions them. Neither is a continuous peak measurement:
short-lived or unobserved reparented processes can be missed. Observed owned
SwapPss was zero, but missing reads and shared-host swap prevent a universal
no-swap or 16 GB suitability claim.

Both owned servers and all four worker processes report joined cleanup, drained
output and no supervisor timeout. Both syntax workspaces were removed. The audit
also found no still-live matching PID/start-time identity among the twenty
observed owned process identities. This does not claim coverage of unobserved
processes.

## Audit identities and remaining gate

The audit rechecked **469 source files, 15 harness files, 26 request files,
26 response files, seven copied blob instances and eleven archived workspace
files**. Large raw prompts, responses, generated files, environment values and
private paths are not reproduced in the durable report.

- Final cohort manifest SHA256: `4155e6338a724e14122c226c368e1a8996b5e11b6d03fd66fc6a7184ff528b52`.
- Frozen harness manifest SHA256: `e1b292780855a17d5109043204f2006350aa8c14642de9abaab11e1ba446e4ed`.
- Memory sample artifact SHA256: `c13af1089686876813a28501bdd58ba777c456fb0ea9cd3c1a5826b64bfc8c25`.

Earlier attempts remain separate. V4 refused an external UV-cache symlink before
server start or inference. V5 reached an HTTP 500 during private profile creation;
separate owned diagnostics identified Ollama's reserved `:local` source suffix.
V6 used neutral `:prepared` tags and verified local source resolution and exact
digests before profile creation. Those setup corrections did not erase earlier
failures or relax the coding gate. The earlier
[CPU corpus](2026-11-07-cpu-corpus.md) retains its original model, source,
denominators and receipt limitations.

The next concrete gap is bounded edit/tool-output recovery on the retained
failures, followed by a separately reviewed unchanged-readiness check before any
new cohort. The six-case/two-repeat evidence, specified 16 GB hardware, native
local-model setup on Linux/macOS/Windows and redistribution review remain unmet.
This no-go does not advertise a shipped included model or promise another run.
