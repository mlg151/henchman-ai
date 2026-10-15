# Issue #2: primary coding agent and dynamic subagents

Status: implementation complete and locally verified; prepared for PR review into `0.4.1`.

The default `tech_lead` compatibility role is now the Primary with `tools: ["*"]`, following live registrations. Explicit saved allowlists replace the wildcard. Each dynamic conversation owns an Agent and isolated execution metrics/controller facade while reusing the existing loop, provider, tool policies, and pool execution claims. Runtime-local tools avoid cross-session manager rebinding. Dynamic delegated scopes contain exactly the requested tool names; nested children cannot widen them.

The manager provides independent conversation IDs/history, custom roles/prompts, FIFO follow-ups, five states, bounded results/events, parent assistance queues, descendant cancellation, and joined shutdown. Parent turns resume on notifications without polling, preserving their transcript and cumulative execution evidence. REPL, Textual, headless, and history/session reset paths join unfinished work. Named-role workflows remain compatible; dynamic children use `invoke_subagent` for nested work.

## Verification

- Final agents/config/contracts/runtime/tool/discovery run: **2,068 passed, 6 deselected** (75.82 seconds). The six known baseline failures are listed below and independently reproduced on unchanged staging.
- Frontend lifecycle regression set: **214 passed**; final relevant frontend rerun: **74 passed**. The 19 new lifecycle checks include real manager/provider-stream cleanup on REPL/headless exit and history reset.
- Workflow/packaging-doc checks: **55 passed** plus one stale Textual mock fixture failure; the fixture was updated for awaited shutdown, and its targeted rerun passed. All **12 offline five-adapter coding-loop cases passed** in that run. No live provider calls or model competence/performance claims.
- Focused saved-scope/prompt/preset/contract review: **121 passed**.
- Ruff passed all touched Python sources/tests. Mypy passed **22 production source files**, with the final cumulative-evidence refinement separately rechecked successfully.
- TDD covered initial missing primary tools and dynamic modules, shutdown failures, and cumulative evidence across reactive resumption before implementation/fixes.

## Existing baseline failures

`tests/config/test_package_surface.py` has three CI-workflow failures on staging: its Python-matrix and wheel/source smoke-job assertions disagree with current main's CI configuration (7 passed, 3 failed). `tests/contracts/test_api_contracts.py` has three API-lifespan failures on staging: mock state is replaced during startup, leaving the API unready without a DeepSeek key (9 passed, 3 failed). These files/assertions and CI were not changed to conceal the failures. No credentials are required for the new feature's tests.

Reference the durable [agent guide](../../docs/agents.md) and [tool guide](../../docs/tools.md) for usage and policy boundaries.
