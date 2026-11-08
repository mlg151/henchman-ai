# Staged delegation local pilot — 2026-11-08

Three bounded local-model attempts did not complete their runs. In the third,
the child staged the requested edit and the parent reviewed and published it;
the resulting file matched the narrow AST oracle, but the run exhausted its
request budget before a final response. It is recorded as incomplete, not as a
successful task or release qualification.

| Attempt | Local requests sent | Runtime | Observed result |
| --- | ---: | ---: | --- |
| v2, concurrent | 9 | 132.144 s | Request limit reached; original file remained. Event capture stopped after the first 100 events, so later tool calls are not available in the report. |
| v3, concurrent | 8 | 123.357 s | Request limit reached; original file remained. Two staged children reported provider connection errors. |
| v4, serialized pilot transport | 10 | 102.520 s | Child completed; parent reviewed and published. The exact AST matched, then the run reached the request limit before completion. |

The attempts used commit `c8b0e43`, a separately installed Linux Python 3.12
development wheel reporting version 0.4.1, and one synthetic addition-function
fixture. The oracle parsed the resulting file and compared its AST to the
expected function; it did not execute generated code. The table reports all
three model attempts, including failures. Two earlier setup attempts sent no
model requests: the transport guard refused the runtime's 4,096-token output
request under an initial 2,048-token ceiling. The later attempts used an
explicit 4,096-token ceiling, ten-request budget and 240-second timeout.

Provider requests were constrained to the already-running local
`qwen38-27b-iq3s` endpoint at `127.0.0.1:8081`; no hosted provider or fallback
was selected. The transport checked the expected model and an idle slot before
each request. The server exposed one slot and was shared, so the checks did not
reserve it exclusively. In v3, slot contention is a plausible explanation for
the children’s connection errors, but the guard did not retain denial reasons,
so the cause is unconfirmed. The v4 test serialized this pilot's own requests
and recorded no transport denials. That serialization belongs to the test
harness; it is not a claim about production provider scheduling. Hardware and
electricity cost were not measured.

The [machine-readable summary](2026-11-08-staged-local-pilot.json) records
counts and hashes; [exact script snapshots](../../evals/staged_delegation_pilot/README.md)
preserve the three executed configurations. The original temporary result files
included raw streamed material and are not committed. These attempts do not
provide the three tasks with two repeats required for a paired comparison,
native-platform qualification, or evidence that delegation improves outcomes.
