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


## PR review (2026-10-15)

Reviewed PR #7 against staging before merge. Fixed two substantive runtime issues:

- **Runtime-control starvation/deadlock:** `manage_subagents(cancel)`, `invoke_subagent`, and dynamic `send_message` previously waited behind the child's source-mutation formatting lock. A child stuck inside a foreground mutation could therefore prevent its own cancellation. Runtime-only coordination now skips mutation formatting/serialization after normal authorization; actual child mutations retain their shared formatter and policies.
- **Budget reset on reactive resumption:** each notification restarted the execution loop with fresh tool counters, allowing notification chains to bypass per-run tool-round and dynamic tool-call limits. Reactive resumptions now carry prior counts into enforcement; explicit new runs retain fresh budgets.

TDD reproduced **4 failures / 5 passes** before production fixes (three blocked control operations and one extra tool execution). Final focused runtime/agent/budget/formatter suite: **73 passed**. Added nested dynamic `max_delegation_turns` coverage and fresh independent-run budget coverage. Ruff passed all six touched Python files; Mypy passed all five touched production modules. Updated the durable agent guide and changelog, including a canonical lifecycle link that also works when the changelog is rendered under `docs/`.

No live provider calls were made. Broader combined staging verification is owned by the parent integration review.

Integrated current staging (`0ec2537`, including PR #5 standards and PR #6 snippet formatting) before push; retained all changelog and roadmap entries. Post-integration focused verification pending.
