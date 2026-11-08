# Staged delegation local pilot — 2026-11-08

Three bounded local-model attempts did not complete their runs. A fourth,
separately budgeted attempt completed the staged workflow and matched the
narrow AST oracle. The incomplete attempts remain in the record; the successful
single-fixture diagnostic does not qualify a release or a paired comparison.

An audit later found that the pilot guard misclassified the primary
`tech_lead` actor and did not enforce the intended prohibition on direct
primary edits. The complete captured parent tool traces for v3–v5 contain no
primary write or edit; v4 and v5 also show the review and publication calls.
The v2 capture ended early and cannot establish its later tool sequence. This
flaw limits the evidence and is retained in the archived scripts.

| Attempt | Local requests sent | Runtime | Observed result |
| --- | ---: | ---: | --- |
| v2, concurrent | 9 | 132.144 s | Request limit reached; original file remained. Event capture stopped after the first 100 events, so later tool calls are not available in the report. |
| v3, concurrent | 8 | 123.357 s | Request limit reached; original file remained. Two staged children reported provider connection errors. |
| v4, serialized pilot transport | 10 | 102.520 s | Child completed; parent reviewed and published. The exact AST matched, then the run reached the request limit before completion. |
| v5, serialized pilot transport | 11 | 119.040 s | With a twelve-request limit, the child completed, the parent reviewed and published, the AST matched, and the run completed. |

The attempts used commit `c8b0e43`, a separately installed Linux Python 3.12
development wheel reporting version 0.4.1, and one synthetic addition-function
fixture. The oracle parsed the resulting file and compared its AST to the
expected function; it did not execute generated code. The table reports all
four model attempts, including failures. Two earlier setup attempts sent no
model requests: the transport guard refused the runtime's 4,096-token output
request under an initial 2,048-token ceiling. The later attempts used an
explicit 4,096-token ceiling and 240-second timeout. The first three model runs
used a ten-request budget; the separately labeled v5 used twelve requests.

Provider requests were constrained to the already-running local
`qwen38-27b-iq3s` endpoint at `127.0.0.1:8081`; no hosted provider or fallback
was selected. The transport checked the expected model and an idle slot before
each request. The server exposed one slot and was shared, so the checks did not
reserve it exclusively. In v3, slot contention is a plausible explanation for
the children’s connection errors, but the guard did not retain denial reasons,
so the cause is unconfirmed. The v4 and v5 tests serialized this pilot's own
requests and recorded no transport denials. That serialization belongs to the test
harness; it is not a claim about production provider scheduling. Hardware and
electricity cost were not measured.

The [machine-readable summary](2026-11-08-staged-local-pilot.json) records
counts and hashes; [exact script snapshots](../../evals/staged_delegation_pilot/README.md)
preserve the four executed configurations. The original temporary result files
included raw streamed material and are not committed. These attempts do not
provide the three tasks with two repeats required for a paired comparison,
native-platform qualification, or evidence that delegation improves outcomes.
