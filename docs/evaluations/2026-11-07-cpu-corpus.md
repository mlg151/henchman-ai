# CPU twelve-case corpus — 2026-11-07

The fixed corpus recorded **eight independently verified successes in twelve
attempts**, three timeouts and one tool-round-limit failure. The frozen acceptance
target was **12/12**, so qualification failed. Every planned case ran once;
no failure was replaced, retried or excluded. This is one local CPU cohort,
not repeated-run reliability or evidence of improvement over another model.

The [bounded evidence projection](2026-11-07-cpu-corpus.json) retains every case,
usage scope, limit, cleanup observation and provenance hash. Raw prompts,
responses, generated files, environment values and private artifact paths remain
outside the published report. The audit read existing evidence only; it made no
model requests and reran no scenarios or oracles.

## Outcomes and denominator

These are the canonical `0.4.2-eval-v1` cases and independent oracles, with fixture
seed 42. The sampler was not seeded; temperature zero does not establish
determinism. Times below are the recorded setup/scenario/oracle/runtime-cleanup,
archive and workspace-removal duration. The JSON separately retains supervisor
duration, which also includes worker startup and final shutdown.

| Case | Profile | Outcome | Seconds | Provider requests |
| --- | --- | --- | ---: | ---: |
| counter-refactor | engineer | 600-second case timeout | 600.89 | 8 |
| add-method-class | engineer | Independent oracle passed | 206.67 | 8 |
| rename-variable | engineer | Independent oracle passed | 148.69 | 6 |
| multi-file-edit | engineer | Independent oracle passed | 178.93 | 6 |
| python-reuse | engineer | 300-second turn timeout | 302.09 | 7 |
| syntax-fix | engineer | Independent oracle passed | 231.92 | 11 |
| fibonacci | basic | Independent oracle passed | 165.71 | 7 |
| test-docs | basic | Ten-round tool limit | 270.13 | 11 |
| package-lifecycle | team | 300-second turn timeout | 302.64 | 1 |
| semantic-bug-fix | basic | Independent oracle passed | 62.82 | 4 |
| tool-failure-recovery | engineer | Independent oracle passed | 154.61 | 4 |
| interruption-recovery | engineer | Independent recovery oracle passed | 239.26 | 7 |

The two 300-second limits are explicit, unchanged scenario limits inside the
600-second whole-case allowance. The package case received no response headers
before cancellation. Counter refactoring and reuse received partial responses
on their final requests. These failures do not establish that a completed
candidate was independently checked and found incorrect. Likewise, model-written
tests or successful tools cannot turn a timed-out case into an oracle pass.

Interruption recovery intentionally uses a one-round first turn, requires observed
work followed by the expected bounded interruption, and then checks the resumed
result independently. Its two turns are one case and remain inside the shared
case/request bounds.

The launcher ran from 2026-11-08 00:39:53 to 01:28:13 UTC, corresponding to
November 7 in America/New_York: 2,899.67 seconds including preflight, process
supervision and profile management. Recorded case durations sum to 2,864.37 seconds.

## Frozen configuration and provenance

Execution used clean source commit
[`add457cd2e6ae1b4debab303bf80d20ce1af5d9f`](https://github.com/mlg151/henchman-ai/commit/add457cd2e6ae1b4debab303bf80d20ce1af5d9f),
the existing baseline runner, canonical role prompts/tools and unchanged oracles.
This was source-checkout execution on Linux with the fixed Python 3.12.13
interpreter used for [revised readiness](2026-11-07-cpu-corpus-readiness-v2.md).
It was not installed-wheel or cross-platform qualification.

The installed base was `ornith1.5:9b`, digest
`fde90266e6077dc19610515813b0065eae248ea2d5ac8064f52e11ca3f5bef3c`,
served by Ollama 0.40.7. Its owned temporary profile set `num_ctx=16384`,
`num_gpu=0`, `num_thread=14` and `temperature=0`. Every observed single-agent
profile and all five preinitialized team roles had a 13,926-token input budget
and a 16,384-token context window; automatic compaction was disabled.

Each case allowed 600 seconds, at most 24 provider requests and at most ten
tool rounds per turn, with the stricter scenario limits noted above. Each request
capped output at 512 tokens, disabled reasoning, and used zero SDK retries.
Tool and delegation retries were also zero. HTTP connect/pool timeouts were five
seconds and read/write timeouts 600 seconds, subordinate to the case deadline.
Cleanup had a separately visible 30-second grace; the worker supervisor allowed
660 seconds. Cleanup grace cannot convert an expired case into a pass.

The corpus admission ceiling was 288 requests and 147,456 requested output
tokens. Those are ceilings, not measured usage. All 80 captured requests matched
the owned model and exact loopback compatible-completion endpoint. The environment
isolated HOME/settings and scrubbed inherited provider credentials; package
preflight used existing offline cache contents. No provider/tool gate denial was
recorded. These controls are not an OS sandbox for arbitrary subprocess networking.

The audit rechecked all 456 recorded source-file hashes and the three frozen
harness hashes, recomputed all 80 request hashes, compared 78 recorded response
hashes, and checked the hashes of all 326 captured workspace files. It also
inventoried 557 case artifact files. Eight workspace entries were omitted or
truncated under the archive limits; raw request/response captures had no observed
byte omissions. The JSON records the original manifest hash and bounded artifact
manifest hashes without publishing private file contents or paths.

## Usage and a retained receipt discrepancy

There were **80 admitted requests**, with server-reported usage on **77**.
Their known sums are **577,925 input tokens and 9,157 output tokens**. Three
requests have unknown usage, so these are partial cohort totals. Baseline
`tokens_in`/`tokens_out` observations describe the final scenario/turn only;
the JSON retains them separately and does not use them as case totals.

Original receipts mark **76 requests complete**. Independent inspection of the
retained SSE bytes finds **77 requests with final usage and `[DONE]`**. The
difference is `test-docs` request 11: its saved receipt marks completion false and
omits the response hash, while the 12,015-byte response artifact contains final
usage and `[DONE]`. Its independently computed SHA256 is
`0e065787b0187c0c7c74a1ac9ecb4e68a0c17f9051b8a2f03bd51f5673d7d94c`.
The request's reported 4,470 input and 314 output tokens were already included
in the saved known sums; the audit does not add them again.

The frozen harness sets completion/hash fields in the stream iterator's `finally`
block. It writes receipts before final client closure, and subsequent flushes
do not overwrite an existing receipt. That ordering permits the observed late
finalization discrepancy. The original evidence remains unchanged, both readings
are retained, and the case remains failed. Future harness sequencing needs a
separate tested correction before another cohort.

Reported local API spend was **USD 0**; hardware and electricity costs were not
estimated. No hosted qualification or hosted-model result is claimed.

## Resources, cleanup and retained earlier attempts

All twelve post-case residency checks reported zero VRAM, 16,384 context tokens
and 6,485,956,360 bytes of model allocation. Allocation is not peak process memory.
The 592 RSS samples selected only two processes named `ollama`; their maximum
combined RSS was 83,824,640 bytes. Coverage of the model runner and owned Python
worker was not established, so this number cannot measure whole-model or
whole-application memory. The host reported 132,210,106,368 bytes of physical RAM.
This is not a 16 GB hardware result.

All twelve worker receipts report joined owned work and removed workspaces;
the audit also confirmed those workspaces are absent. No cleanup error,
supervisor timeout or hard kill was recorded. Final management observations
show the temporary alias absent from both model listings and residency, an empty
resident-model set, and the unchanged base digest. This process/workspace evidence
does not erase the stream-receipt publication gap described above.

An earlier corpus launch aborted during cache copying because the temporary
filesystem exhausted inodes. Its retained post-failure audit and cache-copy
stderr identify a preflight failure before model/profile management or any case
attempt. Disposable partial cache contents were subsequently removed. The original
launcher log was unavailable to this audit; its previously recorded hash is
labeled as such in the JSON. This infrastructure failure remains separate from
the twelve model attempts.

The [failed readiness attempt](2026-11-07-cpu-corpus-readiness.md), separate
[revised readiness](2026-11-07-cpu-corpus-readiness-v2.md), and
[earlier CPU experiments](2026-11-07-cpu-readiness.md) remain retained with their
own denominators. None is substituted into this cohort. The failed fixed target,
single-attempt sample, resource-coverage limits and absent native/hardware evidence
leave included-model qualification open.
