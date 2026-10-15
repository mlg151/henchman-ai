# Interactive question channels and conversational history

Previous goal turn: verified progress (installed wheel + model task evidence).
Current goal remains active; 8GB CPU laptop baseline still unverified.

## Design and ownership

Reuse AskUserTool's optional async callback; bind through ToolManager construction.
Classic REPL owns a serialized prompt_toolkit channel, suspends the key monitor,
and treats answers literally without adding them to command history. EOF is
unanswered, Ctrl+C propagates cancellation, timeout cancels input and releases stdin.
Question/answer messages remain actual tool-call/result pairs in session history.
Textual uses its own core construction and needs a modal channel; implementation
is delegated with real run_test coverage and modal cleanup requirements.
Headless remains unbound and reports unavailable input instead of making up answers.

Remove synthetic THINKING enforcement from conversational transcripts; retain
optional metrics and concrete implementation/tool evidence checks. Separate
NO_WORK_DONE assessment still flags conversation and needs its own contract.

## Evidence so far

- Six question tests failed before root implementation; 27 focused question,
  InputHandler and ToolManager tests passed afterward.
- Real pipe input → actual REPL/tool loop → persisted answer: one test passed.
- Ruff and mypy clean for three root source modules at this checkpoint.
- Worker reports 241 orchestrator/prompt/interruption tests passed after removing
  synthetic THINKING user messages; root integration verification remains pending.

## Local model follow-up

Previous tiny candidates failed task probes. Fetching official Qwen3-1.7B Q8_0
pinned to 90862c4b9d2787eaed51d12237eafdfe7c5f6077 with publisher SHA256/size check.
This is an evaluation artifact only; no product default or managed download added.
Use the same behavioral tasks and bounded CPU context. Host remains 60GiB, so
sampled RSS is not physical 8GB laptop acceptance evidence.

## Integration follow-up

- Actual CLI headless construction also uses Repl; four new format regressions
  exposed interactive binding there. ReplConfig.interactive now explicitly
  disables the callback when RunConfig.prompt is present. All four red→green.
- 67 passed: question channel, CLI app/coverage cases, and five-adapter real-tool
  coding workflow (scripted provider responses).
- 80 passed: REPL, session transcript persistence, chat UI, E2E, AskUser tool suite.
- 31 passed: discovery, help, doctor, documentation consistency. Discovery uses
  runtime-dependent status and explicitly describes headless unavailable input.
- Textual worker: 101 passed across real prompt and nearby UI/integration suites;
  nine tests cover timeout/cancel/serialization/overlay/shutdown/mount failure.
- Worker review found no REPL question-channel defect; real KeyMonitor probe
  found a preexisting bare-Escape buffering issue, now being fixed separately.
- Root mypy five source files clean. One unused test argument was renamed; final
  lint/test gates still to record. Source tests emitted Chroma's Python 3.16
  deprecation warning, not a behavior failure.
- Documentation updated together: docs/tools.md, docs/architecture.md, roadmap,
  TODOS and changelog. Native terminal OS tests and conversational completion
  remain open; no claim of full goal or full-suite completion.

## Final UI verification

- Root combined runtime run: 25 passed (REPL questions, Textual questions, discovery,
  two REPL E2E flows). Textual includes a complete scripted-provider clarification
  through real modal input and disk-reloaded session with matching tool-call ID.
- Bare Escape fix: KeyMonitor flushes incomplete VT sequences after 0.5 seconds of
  input inactivity, resetting the deadline on each fragment. Real pipe tests
  protect split arrow/function keys and monitor ownership after question Ctrl+C.
- Worker terminal/orchestrator regression set: 247 passed; root confirmation and
  installed-wheel rerun are recorded below when finished. Counts overlap.

- Root final terminal/orchestrator set: 109 passed in 6.11s, including concrete
  completion checks. Ruff clean for changed source/tests; mypy clean across 14
  touched production modules. Scoped git diff --check clean.
- Rebuilt and force-reinstalled the wheel into the isolated Python 3.12 environment.
  Expanded installed smoke to include all four new terminal question/monitor test
  modules. **108 passed in 48.93s** outside the checkout, with installed-origin
  checks, both aliases, local RAG, real tools, and scripted-provider workflows.
  See question-wheel-linux-final.log and question-wheel-reinstall.log. The earlier
  82-test pass preceded this expansion. Native macOS/Windows CI remains pending.

## Third model probe outcome and remaining work

- Verified pinned Qwen3-1.7B Q8_0 artifact and ran both CPU tasks. 0/2 passed:
  arithmetic only read files then promised action; reuse never implemented caller.
  Full trajectory and unchanged source snapshots are in
  local-model-probe/qwen3-17b-results.json. Durations55.68s/156.87s; sampled
  model+agent peak2,648,744KiB (~2.53GiB). This60GiBhost is not8GBlaptop acceptance.
  Server exited0 and ps confirmed no llama-server remains.
- Last doc/staging verification:18passed; smoke-script Ruff clean. No source
  changes followed the final source gates and installed108-test pass.
- Full goal remains active: newer small-model evaluation, managed local model
  acquisition/runtime, physical8GBtest, nativeOSCI, provider/live task quality,
  conversational vs implementation completion semantics, stronger Python and
  DevOps/team leadership outcomes all remain. No project commit/staging/push.
