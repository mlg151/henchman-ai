# Local direct versus staged delegation, corrected v2

**Direct execution passed 6/6 attempts; staged delegation passed 4/6.** The
other two staged attempts produced the expected file and reached publication,
but exhausted the 12-request limit before the parent completed, so both are
failures. Four pairs passed in both arms; in two pairs only direct passed.
This small comparison does not demonstrate a benefit from delegation and does
not qualify general-purpose isolated delegation.

| Fixture / repeat | Direct | Requests | Seconds | Staged | Requests | Seconds |
| --- | --- | ---: | ---: | --- | ---: | ---: |
| Addition / 1 | Pass | 4 | 34.24 | Pass | 11 | 115.69 |
| Addition / 2 | Pass | 4 | 30.23 | Pass | 11 | 113.20 |
| Name normalization / 1 | Pass | 4 | 31.40 | Fail | 12 | 164.85 |
| Name normalization / 2 | Pass | 3 | 25.98 | Pass | 12 | 149.69 |
| Voting age / 1 | Pass | 3 | 28.94 | Pass | 11 | 128.91 |
| Voting age / 2 | Pass | 3 | 28.94 | Fail | 12 | 159.20 |

All twelve planned attempts ran, in the frozen alternating order. Direct made
21 requests and staged made 69. Elapsed times include worker startup, review
and cleanup; other offline tests ran concurrently and the local model server
was shared, so the numbers are not isolated latency measurements. The largest
recorded worker peak RSS was 225,844 KiB for direct and 228,084 KiB for staged;
this excludes formatter subprocesses, the model server and GPU. Complete token
usage, hardware cost and electricity were not measured. Inference used only
the local `qwen38-27b-iq3s` alias at `127.0.0.1:8081`; hosted API spend was $0.
The alias does not independently establish the loaded weights.

Both arms used the same synthetic tasks, installed development wheel from
source `c8b0e435eceb229dde930402aab47b628670c139`, 12-request budget and
serialized local transport. Route-specific instructions differ. The direct
arm could edit only its fixture; the staged arm had to invoke a file-only
child, review its proposal and publish it. Publication was auto-approved for
this test; no human review is claimed. Each attempt had a fresh workspace and
home. A local guard checked file paths and actor routes, but it is a test
constraint rather than a general filesystem sandbox.

The [frozen plan and harness](../../evals/staged_delegation_paired/README.md)
describe the limits and reproducibility. The
[retained report, worker records, and output files](../../evals/staged_delegation_paired/results/v2)
include every attempt; the [audit](../../evals/staged_delegation_paired/results/v2/audit.json)
rechecked their hashes, fixed order, route evidence, completion and current
file ASTs. The deliberately narrow AST oracle can reject equivalent valid
solutions and does not execute generated code. Retained events summarize tool
names and outcomes, not complete model transcripts. The separately retained
[invalid v1 cohort](2026-11-08-staged-paired-v1-invalid.md) is not included in
these results.
