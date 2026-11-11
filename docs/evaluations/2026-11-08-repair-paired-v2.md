# Local bounded-repair comparison v2

**Direct execution passed 6/6; bounded repair passed 6/6. All six pairs tied.**
This separately versioned run validates the repaired tool-disclosure path on
source `7141c1f342216b1a24defecb530931ca234f4c41`; it establishes no general
functional advantage, speedup or issue closure. The [v1 result](2026-11-08-repair-paired-v1.md)
remains direct 6/6 and repair 2/6, including all four failed repair outcomes.
The [full v2 receipt and audit](2026-11-08-repair-paired-v2.json) preserve every
attempt, pair, worker result, usage observation and raw-artifact hash.

| Fixture / repeat | Direct outcome | Requests | Seconds | Repair outcome | Requests | Seconds |
|---|---|---:|---:|---|---:|---:|
| addition-repair / 1 | Pass | 4 | 58.656 | Pass | 4 | 91.987 |
| addition-repair / 2 | Pass | 4 | 61.615 | Pass | 3 | 49.975 |
| pricing-repair / 1 | Pass | 4 | 59.677 | Pass | 3 | 54.915 |
| pricing-repair / 2 | Pass | 4 | 64.477 | Pass | 4 | 86.195 |
| already-correct / 1 | Pass | 3 | 64.811 | Pass | 0 | 4.800 |
| already-correct / 2 | Pass | 3 | 66.231 | Pass | 0 | 4.840 |

Times include setup and joined cleanup. Repair ran second in repeat 1 and first
in repeat 2. All 12 fixed attempts completed; none was replaced, omitted or left
`NOT_RUN`. Timing differences were mixed. The already-correct repair controls
made zero model requests after the initial controller check, but their functional
acceptance still tied direct execution. Their raw token fields remain null and
the usage-completeness aggregate remains false because no provider response
exists; this is not an unreported dispatched request.

Each pair used identical initial files, protected criteria, user prompt, fixture
plan identity and explicit settings. The publication audit also compared all 12
saved input files and initial hashes with their v1 counterparts. These inputs
match; **full model messages across versions are not asserted identical**.
Source 7141c1f includes the disclosure fix and intervening default-off delegation,
prompt-note and other changes after v1's source 929dfc0. This is fix validation,
not an isolated ablation or proof that one source change alone caused the result.
Both v2 arms use the same new source.

Both arms register the same read, write, edit and held-plan verification tools.
The direct arm advertises all four. During bounded repair, model declarations
contain only the captured read/write/edit implementations; the controller still
owns verification, and a hallucinated model verifier call remains denied. The
audit checked every saved request's declared tools. In v1, four repair attempts
fixed the source but failed after requesting the controller-only verifier; those
failures remain part of the original negative result.

All 12 retained artifacts passed the independent current-byte AST oracle's
24-point arithmetic grid, all protected criteria stayed byte-for-byte unchanged,
and all four control artifacts retained their original source bytes. The audit
re-evaluated those retained bytes without executing generated Python. Controller
`scoped_pass` and final prose do not substitute for that oracle. These finite
arithmetic criteria are a separate comparison, not general task proof or the
canonical recovery corpus: the pricing case does not require its canonical
failed-then-successful `python_exec` sequence.

All **36 dispatched requests** have complete reported usage, reconciled between
saved SSE responses and runtime actor/run accounting: **218,892 prompt tokens**
and **6,823 completion tokens**. Direct used 22 requests; repair used 14. The
only generation route was the existing local
`http://127.0.0.1:8081/v1/chat/completions`, alias `qwen38-27b-iq3s`.
Hosted API spend was **$0**; hardware/electricity cost was not measured. That local
route assertion is separate from the runtime ledger's unknown catalog pricing.

The borrowed server was neither launched nor configured by this harness; port
8082 was excluded. Each attempt retained a readiness observation of the expected
model and one idle slot. Dispatch guards bind PID/start-time, argv, listener and
model-file metadata, including a final guard before HTTP headers. This is not a
fresh GGUF digest, proof of loaded tensors or exclusive endpoint reservation.
The shared server's warm state and other possible callers limit timing claims.

Per attempt, the bounds were 300 seconds including setup, plus a 30-second
cleanup allowance; 12 shared requests including retries/descendants; 10 tool
rounds; two repair attempts and identical-failure limit two; zero SDK/delegation
retries; 4,096 output tokens; 32,768 application context tokens and a 27,852-token
approximate serialized-input budget. All worker, stream/SDK and output-reader
cleanup receipts joined. The audit found all exact captured worker PID/birth
identities absent afterward. Process samples cover workers and observed
descendants only, exclude the borrowed server/model/GPU, and include nine missing
sample observations. They do not qualify total memory, continuous peaks, CPU-only
execution or a 16 GB machine.

The unchanged historical offline evidence records 27 fault tests on each of
Python 3.11 and 3.12 plus 12 accepted synthetic dry attempts. Live provenance uses
Python 3.12.13 and pinned package versions. Offline checks establish harness
boundaries, not model quality. The receipt's `qualification_pass` means only
harness/oracle acceptance; it is not release qualification.

The [archived reproduction notes](../../evals/repair_paired_v2/REPRODUCE.md)
explain the 27-file archive, including all 13 exact Python files and historical
metadata. Publication verified all 26 frozen input hashes, all 1,690 source-file
hashes and four internal symlink targets. The source archive/tree, Python caches
and private approved admission are excluded from the repository. All **270 raw
artifacts** are inventoried by hash; the original **268 v1 artifacts** were also
rechecked unchanged. Publication made no endpoint calls and reran no experiment.
