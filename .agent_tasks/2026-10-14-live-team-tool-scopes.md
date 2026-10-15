# Live team tool scopes

The previous goal turn was progress: context-sized discovery was implemented and
verified. This turn adds explicit leader authority, live tool membership and
acting-agent dispatch. The full industry-leading coding-agent objective remains
active and unproven.

## Changes

The leader now uses its merged configuration's tool allowlist and local automatic
approvals. The default preset includes plan verification for the quality-gate
workflow and delegates file-edit tools to specialists. It retains shell, git and
knowledge operations, so documentation now describes its actual capabilities
without claiming enforced read-only execution. Custom lists gain no implicit
file tools, verification or delegation access.

ScopedToolRegistry provides a fixed copied allowlist over a live parent registry.
Allowed late registrations, removals and replacements affect lookup, inventory,
declarations and authorization consistently. Local overrides/exclusions stay
local; explicit extra tools take precedence. Builtin search copies bind lazily to
each scope and refresh when their source changes, including discovery priorities.
Plan mode and confirmation policies remain live. Specialists retain local
explicit automatic approval; the new leader scope also follows root automatic
approval decisions to preserve its previous acting-registry policy semantics.

Both terminal fallback ToolExecutor and standalone JSON dispatch now execute
against agent.tool_registry, including approval classification. Test doubles carry
that registry explicitly; production has no fallback to root permissions.

Orchestrator initialization retains an explicitly provided empty registry rather
than replacing it based on its false truth value. This is required for tools
registered after startup to reach the intended parent. Engineer evaluation logging
resolves a local search wrapper before restoring its known discovery identity.

## Evidence

- Leader regression before implementation: 4 failures / 1 pass. Additional empty
  registry regression observed the original parent being discarded before repair.
- Actual OpenRouter SDK-scripted workflow first allowed an unlisted leader edit
  to change arithmetic.py to return a+99; its independent final artifact assertion
  failed. After scoping, all five adapters reject that edit, delegate the repair,
  run failing then passing tests, review reuse and execute plan verification.
  Original positive workflow assertions remain and are tested alongside denial.
- Live-scope worker observed 10 failing contracts before implementation, then a
  separate stale-priority regression. Its final 107-test gate passed.
- CLI worker observed 6 new denied/allowed/classification regressions before
  implementation; its 97-test gate passed, including cancellation/result balancing.
- Actual initialize_mcp path with a stub connection registers two tools after the
  leader and specialist exist: allowed tool executes from both scopes, excluded
  tool stays inaccessible, and scope search reveals only the allowed entry.
  No network or model inference is used for this test.
- Final focused source integration: 297 passed in 34.93s;
  live-team-scopes-source.log. Default/custom leader, late tools, policies,
  discovery, evaluation profile, model switching, CLI fallbacks, and five-adapter
  coding workflows are included.
- Ruff: 14 source/test/helper files clean. Mypy: 11 source/helper/test files clean.
  Existing test_output_stream_coverage.py has a malformed noqa warning reported
  by its worker; no whole-tree static-clean claim.
- Independent review found no actionable defect and ran 43 focused tests across
  live scopes, leaders, actor dispatch, discovery and evaluation wrappers.
- Installed-wheel suite: 896 passed in 62.38s outside the checkout. Both CLI
  aliases and local RAG smoke passed. Log: live-team-scopes-wheel-linux.log.
  One existing anyio marker warns because that mark is not registered in the
  isolated smoke configuration; pytest-asyncio auto mode executes the tests.

The new wheel was built and forceinstalled into portable-wheel-env (Python3.12)
then checked outside the source checkout; source verification uses Python3.14.
Artifact: live-team-scopes-wheel/henchman_ai-0.3.17-py3-none-any.whl.

## Remaining work

These tests establish scoped execution and SDK-scripted recovery, not live team
competence or task correctness. Live Python task success, broader reuse and DevOps
outcomes, long-turn context/memory behavior, native Windows/macOS hosted results
and a physical 16GB laptop test remain open. Custom leader model/prompt settings
and runtime configuration reload deserve a separate end-to-end audit; this slice
verified tool and approval settings.

No cloud model calls, owned model servers, staging, commits, push or deployment.
The unrelated user's runtime processes were not changed. Changes remain in the
shared working tree. Do not mark the goal complete from this checkpoint.
