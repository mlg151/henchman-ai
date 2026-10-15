# Delegation limits and verification guidance

The previous 700K-capacity live team run inspected, implemented and reviewed the
fixture, but exhausted its deadline without the explicitly required `pytest_run`
evidence. Its source predates the final-handoff parser fix. Keep that report as
the baseline; do not relax the independent scenario criteria.

## Contracts

- Compute specialist limits for each execution from current runtime settings and
  the actual cached agent. Describe individual requested calls and tool batches
  separately, including their different stopping behavior. Preserve enforcement.
- Keep runtime limits out of persistent prompts and static delegation briefs.
- Shared verification guidance must accept available structured test/lint tools,
  respect explicit tool requirements and retain observed pass/fail evidence.
- Preserve role scope, custom prompts, source reuse and independent review gates.

## Execution and ownership

1. `completion_contract` owns `delegation.py` and a new focused request-level
   regression file. Observe RED, implement disclosure, verify cached-agent reuse
   and nearby round-budget contracts.
2. `workspace_prompt_refactor` owns only byte-preserving extraction of repeated
   `VERIFICATION_LOCK` literals in `prompts.py`. Freeze after comparing constants
   and rendered prompts. Root then changes the shared policy and contradictory
   shell-only verification instructions, with existing prompt/runtime tests.
3. Root updates `docs/agents.md`, changelog and roadmap, and stages the new test
   into the installed-wheel test bundle if needed.
4. Run focused source tests and static checks. Independent reviewer checks limit
   semantics, cached reuse, prompt contradictions, evidence integrity and scope.
5. Run one bounded live OpenRouter integration probe under the existing 700K
   context/24-request/480-second/zero-retry bounds with a new durable report.
   Load the authorized key in memory only. Report outcome, timing and usage
   honestly; this combined integration sample is not a controlled latency study.
6. Build a fresh wheel and run relevant installed-package coverage if source or
   staging changes require it. Record precise outcomes and remaining goal gaps.

## Review boundaries

No deployment, publishing, staging, commits, enforcement changes, speculative
prompt overhaul, model calls by workers, or task-quality claims from runtime
status alone. Preserve all preexisting dirty-worktree edits.
