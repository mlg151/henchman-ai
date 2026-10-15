# Production team Python evaluation

Previous turn was progress: configured shared leader, actor routing and protected
execution lifecycle were implemented and verified (549 source /1089 wheel tests).
The full coding-agent goal remains active. This slice makes actual team task
quality measurable through the production runtime; scripted checks only validate
the harness, not live model capability. Credential-presence inspection found no
OpenRouter environment or saved key/reference/model. No live model calls planned.

## Design and contracts

Extend the existing EvalTestRig with explicit profile='team'. Keep basic and
engineer behavior/constructor compatibility. New optional settings: Settings
parameter is copied and only supported in team mode. Team mode rejects explicit
core AgentConfig or custom system_prompt rather than silently dropping knobs.
Use real ToolManager registration/available builtin filtering, production
Orchestrator, canonical role scopes/prompts and existing headless adapter. Shared
tool assembly may be extracted once; no parallel provider/agent factory.

ToolLog and EvalResult may move to evals/models.py with explicit compatibility
reexports from helpers.py. Append optional actor/call-id fields to ToolLog;
team token totals are None when unavailable, never invented zero usage.
Keep existing single-agent semantics. Bound iteration limits across all team
agents (preinitialize configured enabled roles if necessary, record that fact);
retain delegation depth/turn/retry limits and whole-turn timeout. Evaluation
workspaces are temporary and auto-approved, not OS sandboxes, and runs are serial
within a process because the existing rig changes process CWD.

Team action logs come from actual request/result events correlated by
(source_agent, tool_call_id), preserving request order, failure, args and results.
This includes intercepted delegation and avoids duplicate wrapper observations.
Only leader content contributes to final_response. Preserve recovered child
errors as diagnostics; successful execution uses authoritative outer completion.
Preserve genuine root failure and timeout/cancellation cleanup. Expose copied
profile metadata with per-role prompt digest/size, scoped tool names, actual
provider/model and context/output/round/delegation limits without credentials.

Public runtime API remains EvalTestRig(provider=..., profile='team', settings=...).
run(prompt,max_iterations=25,timeout=300) returns EvalResult as before.
Expose orchestrator read-only for team setup/tests; fail explicitly otherwise.

Scenario API in evals/test_team_python_workflow.py:
async run_team_python_workflow(rig: EvalTestRig, *, max_iterations: int=25,
timeout: float=300) -> dict[str, Any]. Return JSON-serializable report even for
runtime/oracle failure, with success false and task_verified false. Include
scenario/version/spec digest, runtime outcome, attributed action observations,
independent checks and source fingerprints. No provider keys or raw settings.
The explicitly opt-in live pytest test asserts report['success']; leave default
basic/engineer eval behavior unchanged.

Reuse existing normalization/unique-label fixture semantics and independent helper
call verification. Add a small Python CLI calling unique_labels, accepting argv
labels and returning a JSON array; no args prints [] and unsupported option exits2.
Require repository inspection before implementation, an engineer edit, a real
post-edit test execution, and another specialist's subsequent review. Match roles
and results flexibly; do not hardcode one model tool/delegation order. Preserve
provided helper/tests/check config bytes. Do not accept narrative '4 passed' as
independent correctness or model verification evidence by itself.

Independent checks use existing bounded subprocess / Python verifier / acceptance
observations. Pin Ruff selection/format and strict mypy settings independently of
model-edited project config. Check helper reuse through monkeypatch observation,
Unicode/order/duplicates/input preservation, fresh CLI child success/invalid-input
behavior and invocation from another working directory. Guard false passes from
fixture edits, unchanged stub, duplicated helper, fabricated output, lone-agent
implementation and correct files followed by root failure. Explain precise quality
and CLI scope; do not call it smell-free, deployment-ready, or fully verified.

Report runner API: python -m evals.run_team --provider openrouter --model ...
--context-length N --max-iterations N --timeout N --report PATH. Use shared saved
provider configuration (load before temp-CWD setup), no fallback/cloud call absent
credentials. Resolve report destination before setup; retain failure diagnostics
and report outside workspace cleanup. Reject invalid limits before provider lookup.
Record actual setup metadata, requested limits, scenario outcomes and duration.
Use nonzero exit for configuration/runtime/independent-check failures. Report
usage/cost unavailable until actually measured; no fabricated totals or ranking.

## Ownership

- Runtime worker: evals/helpers.py, new evals/models.py/team_runtime.py as needed,
  new tests/testing/test_team_eval_profile.py. TDD red first; preserve existing
  eval helper/profile contracts and source scopes/discovery.
- Scenario worker: evals/test_team_python_workflow.py and new
  tests/testing/test_team_workflow_oracle.py; may refactor fixture/oracle helpers in
  evals/test_python_reuse.py only when shared logic is needed. Do not edit rig.
- Root: evals/run_team.py + new runner contracts; docs, roadmap, changelog,
  installed-wheel test staging and final integration. Coordinate interface changes.
- Independent review after implementation, using original goal and these contracts.

Shared worktree: preserve others' edits. No new dependencies, cloud model calls,
staging, commits or deployment. Scratch artifacts stay in .agent_tasks.

## Verification

- Write focused failing team runtime, scenario false-pass and report-runner tests.
- Run meaningful focused helper/profile/oracle/recovery tests and Ruff/mypy on
  touched implementation. Keep original single-agent assertions intact.
- Run scenario through real tools with scripted models, including errors/retries
  and independent subprocess quality/CLI checks. Script success is harness proof.
- Build fresh wheel, forceinstall in isolated Python environment, stage relevant
  eval/runtime tests outside checkout and verify actual package origin.
- Record exact pass counts and limitations; keep overall goal active.

## Steering and review evidence

User subsequently identified the OpenRouter key in ~/.bashrc. A safe parser found
one literal export without printing or persisting its value. Read-only auth/key
check returned200. Public model metadata confirmed xiaomi/mimo-v2.6-pro tool
support and current pricing; a single bounded live probe was started with24
global requests,32K raw context,8192 output tokens/request,12 rounds/agent,
480-second deadline, zero SDK retries, zero delegation retries and provider
max_price routing filters. Script contains no credentials. Live handle19004;
log team-python-live-mimo.log; report/artifacts names in the probe script.

Independent review reproduced and owners fixed partial/lazy role client leaks,
client-close cancellation masking the primary failure/CWD cleanup, and ambiguous
outstanding actor/call-ID correlation. Runtime and runner regressions cover them.
The scenario also rejected same-batch read/edit temporal false passes using
event indices, and samples final fingerprints after independent checks.

A later review reproduced shell changes after pytest/review bypassing named-edit
ordering. Runtime owner is adding keyword-only observe_event callbacks after
event retention/correlation for every profile; callback errors must propagate
unchanged after stream cleanup/limit restoration. Scenario owner snapshots known
artifacts on events with bounded reads; testing/review must follow the last
actual implementation change. Readonly later commands remain acceptable. The
already-running live process uses the pre-observer scenario; let it finish and
label that scope rather than silently restarting or counting it as post-fix proof.

## Final checkpoint

The live version 1 probe failed at 480 seconds after 17 requests; generated artifacts
passed independent checks, while post-edit pytest and specialist review were
absent. Version 2 now observes bounded artifact snapshots, rejects late shell and
engineer Python edits without renewed verification, and accepts unrelated notes.
Fresh gates: 178 focused source tests; 1,172 isolated Linux installed-wheel tests;
Ruff on 8 files and mypy on 7 files clean. Full evidence and remaining limitations are in
`2026-10-14-team-python-evaluation.md`. Overall goal remains active; no further
model calls, commits or publishing occurred.
