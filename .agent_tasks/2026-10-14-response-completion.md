# Response delivery and execution evidence

Previous goal turn: verified progress on completion failure integrity, with 312
source checks and 180 installed Linux wheel checks. Full goal remains active.

## Contract

- `CompletionRequirement` is a Python 3.11-compatible StrEnum: response/actions.
  `Orchestrator.run` and `run_direct` default to response; callers can explicitly
  require actions. AgentLoopParams and delegated work default to actions.
- RESPONDED requires zero attempted tools, normal STOP, and a final committed
  assistant message with visible nonempty content and no tool calls in the current
  turn transcript. Failed/stalled/timed_out take priority. Empty responses, old
  messages, private reasoning, and failed-tool apologies cannot supply success.
- A promise may be a response but is never verified task completion. Explicit
  actions requirements reject it. COMPLETED remains coarse successful execution,
  with UI label 'finished execution' instead of 'completed work'.
- Completion events contain canonical task_verified=False and evidence with
  tool_calls, successful_tool_calls, response_complete, completion_requirement.
  Missing runtime state yields evidence=None, not invented counts. JSON FINISHED
  output has top-level task_verified=False while preserving its original data.
- delegate_task declares completion_requirement actions/response; arguments are
  validated and propagated into the actual specialist loop. Only explicit
  response accepts RESPONDED. Parsed claims cannot override runtime metadata.
  Tool results and ledger text state that task verification is not established.
- Unbound delegate_task now returns unavailable instead of fake success. Actual
  orchestrator interception still runs specialists. Direct headless JSON uses
  unbound registry execution, so that path cannot yet coordinate a team.

## Review corrections

Independent review reproduced internal stall retries reusing earlier CONTENT
after an empty final response. Completion now checks the committed final message,
not accumulated stream fragments. Its regression failed before the fix.

Review also reproduced stall failure/count leaking to the next run. New run and
clear_history reset only turn-local stall evidence; enabled/max-nudges settings
and detector identity survive. Tool continuations retain current-turn evidence.

## Verification

- Initial response suite: 15 failures before implementation, then passed.
  response-completion-red.log.
- Internal retry regression: failed before fix, response-stall-retry-red.log.
- UI/JSON regressions: 14 failures before fix; worker nearby suite 203 passed.
- Stall lifecycle: 5 failed/1 passed before fix; 64 focused core checks passed.
- Delegation requirement/evidence: 84 focused checks plus 66 compatibility checks
  passed. Invalid options reject before specialist execution; forged report
  fields cannot replace canonical status/evidence.
- Unbound direct tool and registry tests both failed before fix; 19 tool/public
  delegation checks passed afterward.
- Final combined source suite: 488 passed in 6.09 seconds; existing Chroma
  deprecation warning only. response-completion-final.log.
- Ruff clean; mypy 16 runtime modules clean plus the separately checked delegate
  tool; scoped diff checks clean. This does not claim a full repository run.
- Fresh wheel built and force-reinstalled in isolated Python 3.12 environment.
  Installed Linux check passed: 247 tests in 27.83 seconds, both CLI aliases and
  local RAG operations. Runner asserted installed package origin and staged tests
  outside the checkout. response-completion-wheel-linux.log. This is not native
  Windows/macOS, physical8GB hardware, or live model quality evidence.

## Remaining full-goal requirements

Task verification is not implemented by the new false flag. Typed acceptance
checks, durable evidence and independent checks of actual task correctness remain
open. A successful read still counts as execution activity, never proof that a
coding change happened or worked. DevOps/team outcome evaluation, live-provider
quality, included local default selection, physical CPU-only8GB acceptance and
native Windows/macOS verification remain required. No staging, commit, push or
publication occurred.
