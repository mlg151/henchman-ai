# Completion integrity

Previous goal turn: progress, with source and installed-wheel proof for bounded
Python quality analysis. The full coding-agent goal remains active; CPU-only 8GB
laptop operation and a useful included local model remain unverified.

## Scope and evidence

Read-only exploration found that any successful tool could conceal a later
provider error, parsed specialist STATUS overwrote runtime status, and nested
tool results counted as parent successes. A failure could also be marked done
in the ledger and both terminal UIs. These are prerequisites to a broader
conversation-versus-task completion contract, not substitutes for it.

- New `failed` completion status records provider ERROR events and abnormal
  FINISHED reasons, including length and content-filter stops. Tool dispatch,
  cleanup and cancellation exceptions mark the loop failed; top-level exceptions
  also update public last_completion_status before propagating.
- Per-agent LoopState evidence prevents another agent's finalization from
  replacing its assessment. Legacy out-of-loop assessment still supports the
  existing orchestrator count fields.
- Successful tool results count only for pending IDs and the owning source agent.
- Delegated runtime status overrides parsed report fields; only the requested
  target establishes completion. Ledger/tool results require explicit completed
  and no observed runtime error. Missing/unknown/failure outcomes stay unsuccessful.
- Shared result formatter labels unsuccessful outcomes for the lead and ledger.
- Classic/Textual UI require explicit completed to render success. Headless text
  exits 1 for failed/stalled/timed_out and retains 2 for no_work_done.
- Updated completion schema, nearby architecture docs, roadmap and changelog.
- Four provider contract mocks now use the existing SDKResponse helper and assert
  awaited stream closure; production provider behavior was not changed.

## Verification

- Initial runtime regressions: 9 failed before implementation.
  `completion-integrity-red.log`.
- UI regressions: 9 failed before fix; worker's nearby suite 132 passed.
- Delegation formatting: 17 failed/3 passed before fix, 20 passed after;
  combined worker delegation suites 70 passed.
- Independent review reproduced a dispatch exception retaining successful state;
  regression failed before fix. Additional assertion reproduced stale public
  status before its fix. Logs: completion-dispatch-red.log and
  completion-exception-status-red.log.
- Final source suite: 312 passed in 5.32 seconds, existing Chroma deprecation
  warning only; completion-integrity-final.log. Covers real orchestrator/tool/
  delegation paths, nested IDs/targets, error recovery, CLI exit/rendering,
  interruption, transcript preservation, contracts and docs.
- Ruff clean for changed runtime/tests; mypy clean for 9 runtime modules, with
  execution module rechecked after the last change. Scoped diff checks clean.
- Broader exploratory contract run initially had 12 failures/835 passes;
  eight were new fixture/expectation mismatches, four stale SDK mock contracts.
  Each failure was repaired and its corresponding focused suite passes. This
  does not claim a subsequent whole-contract-suite or full repository pass.
- Final wheel built and force-reinstalled in isolated Python 3.12 environment.
  Final installed Linux verification: 180 tests passed in 26.99 seconds, both CLI
  aliases and local RAG operations passed. Tests were staged outside the checkout
  and asserted installed package origin. Log:
  completion-integrity-wheel-linux-final.log. This is not native macOS/Windows,
  live-model performance, or physical 8GB acceptance evidence.

## Remaining requirements

Ordinary no-tool conversation still receives no_work_done. Successful reads still
qualify for the coarse completed execution status; this is not proof of requested
implementation, behavioral correctness, or verification quality. Explicit task
expectations and evidence-backed task completion remain open. DevOps/team outcome
evals, live-provider quality, local-default selection, physical8GB memory/runtime
acceptance and native Windows/macOS execution remain required. No staging, commit,
push or publication occurred.
