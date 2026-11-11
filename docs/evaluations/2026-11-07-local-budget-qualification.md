# Local budget admission and restart retention — 2026-11-07

One local provider request failed without content or final usage. Its consumed
request and uncertain token hold survived both a second invocation and a fresh
Python process. Both follow-up invocations were denied before HTTP. The
[redacted evidence](2026-11-07-local-budget-qualification.json) records all three
outcomes, stable run/attempt identities and ten passing accounting checks.

The public `Orchestrator.run_direct()` path used an isolated role with no tool
declarations, an active goal, `SessionManager` persistence and a separate SQLite
accounting store. Read-only discovery found `qwen38-27b-iq3s` on the existing
`http://127.0.0.1:8081/v1` server. The qualification made exactly one streamed
completion request, with an eight-token output cap and requested trailing usage.
It used a one-request limit, a USD 0 money limit, and explicit zero input, output,
cache-read and cache-write rates dated 2026-11-07. No user server was restarted,
reconfigured or modified; no paid endpoint or fallback was used.

| Invocation | Forwarded HTTP requests | Outcome | Retained accounting |
| --- | ---: | --- | --- |
| First process, initial turn | 1 | Error after 100.199 seconds; no content or final usage | 1 consumed request; 53 tokens held; usage unknown |
| Same process, second turn | 0 | `request_limit` | Same run and attempt; unchanged hold |
| Fresh process, restored session | 0 | `request_limit` | Same run and attempt; unchanged hold |

The first failure coincided with the configured 100-second SDK timeout, within
the 110-second outer deadline. The harness retained the error-event count but
not its text or underlying exception class, so the exact error remains
unverified. The 53-token hold consists of 45 estimated input tokens plus the
eight-token output reservation; it is not reported provider consumption. The
held monetary estimate is explicitly USD 0, while settled estimates and reported
billing remain unavailable. The transport allowed only the exact local URL,
disabled redirects and retries, and would reject extra HTTP attempts. Neither
follow-up reached that safety gate: accounting denied both first.

The first process recorded source commit
`fe0d1c1b984092a7707f0503814894b146cdc94e`, Python 3.11.15, installed package
version 0.4.1 and OpenAI SDK 2.21.0. The shared checkout had concurrent uncommitted
work, so this is not a clean-checkout release qualification. The retained JSON
contains configuration, timing, process IDs, price provenance and the harness
digest; prompts, response text, headers and credentials are omitted.

This establishes live unknown-usage retention and admission denial across
restart. Successful live final-usage reconciliation remains unqualified by this
attempt. It provides no coding-quality or broader model-readiness result.
