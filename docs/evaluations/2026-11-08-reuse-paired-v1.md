# Repository reuse paired experiment: incomplete local run

The fixed comparison did **not** produce a pair. The first baseline attempt
timed out after 300 seconds, its owned worker and readers were joined, and the
borrowed local server was still busy at the next readiness check. The harness
stopped with 11 of 12 planned attempts unrun. No attempt was replaced or
retried. There is no candidate-arm result and no evidence that repository
retrieval improves reuse. Issue #17 remains open.

The source was `d195ac18d3c2d586e30f29f218c7813e97c97269`; the harness and
its limitations are [preserved here](../../evals/repository_reuse_paired_v1/README.md).
The selected server was the local `qwen38-27b-iq3s` endpoint. The harness
dispatched seven local requests; six returned complete usage, totaling 46,180
reported prompt tokens and 3,994 reported completion tokens. The seventh did
not report complete usage, so total token use is unknown. No hosted endpoint
was used; hardware cost and server resource peaks were not measured.

The final file passed the narrow independent helper-reuse oracle, but the
attempt was not accepted. The only earlier verifier run rejected an older file
version as outside the interpreter's supported AST subset; the file changed
afterward without a completed current verification. A requested read of
`.henchman/plans/verification.json` was also denied by the fixed fixture
guard. These are observed outcomes under this restricted harness, not proof
that the generated code is generally correct or incorrect. The borrowed
server was neither stopped nor reconfigured.

A later, separate prototype correction added support for unshadowed empty
`set()` calls. With that correction, the earlier version of the file (SHA-256
`34a6e9a53e99d9bcbac7c9297749ea2e888fd570b32be9be9165fc7b4b6124c2`)
passes the prototype oracle's finite behavior and helper-call checks. This
post-run observation does not change the original verifier failure, the
timeout, or the missing candidate-arm results.

The retained receipt has SHA-256
`ec628414281744197636ea11b00d98e1dbeb196d62a052d5c81298888cd1b92e`.
An independent audit of the receipt, worker settlement, inputs, and 77 raw
files has SHA-256
`00fa831f17b2265762c91b423055576ff7c74962920209ff64e9d7097c5fd92c`;
the raw files and audit remain in the local release-qualification cache.
The [synthetic preflight](2026-11-08-reuse-preflight-v2.md) is separate and
does not supply the missing live results.
