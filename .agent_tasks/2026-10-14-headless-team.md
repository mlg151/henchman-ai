# Headless team execution

Previous goal turn: progress, typed acceptance observations implemented and
verified (182 source /329 installed Linux wheel checks). Full goal remains active.
Target is an8GB CPU laptop; actual host has60GiB and no physical8GB evidence.

## Implemented

- Actual Repl JSON/json-complete/stream-json routes through its existing
  Orchestrator.run/run_direct, preserving provider/pool/tool configuration.
  --agent is passed through all formats. Standalone evaluation runtimes without
  a real orchestrator retain their prior bounded agent loop.
- cli/headless.py forwards nested events, suppresses provider FINISHED events,
  requires source=orchestrator, expectedrole and scope=run on outer completion,
  and emits one terminal result. Completed/responded succeed; missing or other
  status fails. Nested errors can recover. Exceptions force a failed terminal;
  cancellation/render errors preserve original exception and close streams.
- finalize_run marks completion scope=run; direct runs now initialize a fresh
  ledger/metrics via prepare_run. Child completions cannot impersonate root.
- JSON serialization conditionally includes source_agent, preserving attribution
  when different agents reuse tool-call identifiers. task_verified stays false.
- Shared ExecutionController bounds each agent's batches by base_tool_iterations;
  permits final answer after last allowed batch and settles rejected requests.
  Existing delegation call/depth caps remain separate. Own successful/failed
  tool results update agent.turn immediately, and completed batches increment
  turn.iteration. Nested same-ID results do not count as parent work.
- Registry.authorize is reused by execution and delegation interception; delegate
  must be registered in the caller's scope. DelegateTaskTool is EXECUTE. Denials
  produce correlated failure results before specialist model invocation.
- create_scoped_registry links to parent policies dynamically; cached/nested
  scopes see changed plan mode and confirmation handlers. Scope-local explicit
  auto-approvals remain honored. Standalone delegate remains unavailable.

## Tests and review

Root new tests/e2e/test_headless_team.py exercises five actual provider adapters
with scripted SDK transports, in events and json-complete modes. It creates real
Python fixtures, delegates explorer research -> engineer implementation (failing
then passing subprocess tests) -> explorer review, preserves the existing helper,
and runs typed acceptance checks. Asserts actual edits, unchanged helper, shared
provider reuse, ledger outcomes, confirmations, attributed child results,
4 parent calls/rounds, and single unverified final completion.

Initial root test failed at3 instead of14 provider calls before routing changed.
Root scope/direct-state tests failed before fixes. Worker tests exposed unbounded
orchestrator rounds and delegation policy bypass (a real marker subprocess could
run despite plan mode/denial); regressions now pass.

- Combined final focused source gate:207 passed in18.82s, Python3.14.
  .agent_tasks/headless-team-source-final.log
- Separate app compatibility worker:92 tests passed.
- Policy worker:158 focused/existing tests passed.
- Shared loop worker:224 nearby tests passed plus final9 budget cases.
- JSON provenance worker:32 tests passed.
- Independent final review: no concrete remaining blocker;31 final adapter/budget
  tests passed. This review checked current dynamic policy implementation.
- Documentation contract gate:13 passed.
- Ruff clean for touched runtime/new tests. Root mypy11 runtime modules clean;
  workers separately checked delegate/adapter modules and applicable tests.
- Fresh wheel built, force-reinstalled into isolated Python3.12 environment,
  tested outside checkout with installed origin assertion:385 passed in46.27s,
  both CLI aliases and local RAG operations passed. All process handles terminal.
  .agent_tasks/headless-team-wheel-linux.log
- No full-repository, hostedCI, nativeWindows/macOS, real-model quality,8GB
  performance or industry-leading outcome claim. No staging/commit/push.

## Follow-up considerations / full goal still open

The orchestrator currently buffers a tool batch's nested events before yielding
that batch; this milestone does not certify real-time child-event latency or
bounded aggregate event-buffer memory. The JSON outer finish now reports runtime
status/evidence rather than the standalone provider usage payload; provider token
usage/cost reporting deserves explicit aggregation work. Interrupted transcripts
are balanced, but cancelled consumers are not guaranteed further rendered events.

Live Python/team/DevOps correctness and quality evaluations, independent semantic
acceptance, competitive measurements, provider quality/cost, local model selection,
physical8GB CPU memory/latency and native platform verification remain open.
