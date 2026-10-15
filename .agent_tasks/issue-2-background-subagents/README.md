# Issue #2: primary coding agent and dynamic subagents

Status: implementation complete and locally verified in PR #7 targeting `0.4.1`. Current main's independently merged CI PR #4 is included in the branch.

The default `tech_lead` compatibility role is now the Primary with `tools: ["*"]`, following live registrations. Explicit saved allowlists replace the wildcard. Each dynamic conversation owns an Agent and isolated execution metrics/controller facade while reusing the existing loop, provider, tool policies, and pool execution claims. Runtime-local tools avoid cross-session manager rebinding. Dynamic delegated scopes contain exactly the requested tool names; nested children cannot widen them.

The manager provides independent conversation IDs/history, custom roles/prompts, FIFO follow-ups, five states, bounded results/events, parent assistance queues, descendant cancellation, and joined shutdown. Parent turns resume on notifications without polling, preserving their transcript and cumulative execution evidence. REPL, Textual, headless, and history/session reset paths join unfinished work. Named-role workflows remain compatible; dynamic children use `invoke_subagent` for nested work.

## Verification

- Refreshed agents/config/contracts/runtime/tool/discovery run after CI PR #4: **2,073 passed, no exclusions** (75.89 seconds). Earlier development checks had 2,068 passes with six independently reproduced baseline failures excluded; those baseline failures were addressed separately by PR #4, as described below.
- Frontend lifecycle regression set: **214 passed**; final relevant frontend rerun: **74 passed**. The 19 new lifecycle checks include real manager/provider-stream cleanup on REPL/headless exit and history reset.
- Workflow/packaging-doc checks: **55 passed** plus one stale Textual mock fixture failure; the fixture was updated for awaited shutdown, and its targeted rerun passed. All **12 offline five-adapter coding-loop cases passed** in that run. No live provider calls or model competence/performance claims.
- Focused saved-scope/prompt/preset/contract review: **121 passed**.
- Ruff passed all touched Python sources/tests. Mypy passed **22 production source files**, with the final cumulative-evidence refinement separately rechecked successfully.
- TDD covered initial missing primary tools and dynamic modules, shutdown failures, and cumulative evidence across reactive resumption before implementation/fixes.

## Historical baseline failures, resolved separately

The original baseline reproduced three CI-workflow/package-surface failures (7 passed, 3 failed) and three API-lifespan/readiness failures without a DeepSeek key (9 passed, 3 failed). During development, independently merged CI PR #4 aligned the CI contract tests and supplied default fake test credentials. The branch now includes that current main base, and its full relevant suite passes without exclusions. No feature change weakened CI/API assertions to conceal a regression, and the new runtime tests make no live provider calls.

Reference the durable [agent guide](../../docs/agents.md) and [tool guide](../../docs/tools.md) for usage and policy boundaries.
