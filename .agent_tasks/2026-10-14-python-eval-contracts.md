# Python evaluation contracts checkpoint — 2026-10-14

The user resumed the active coding-agent goal after pausing. The goal currently
focuses on provider-independent Python development, code quality, reuse, DevOps
and team leadership. This turn made concrete progress; the overall goal remains
active and is not proven complete. No additional model selection or downloads
were performed.

## Implemented and reviewed

`evals/helpers.py` now records immutable scalar outcomes for each agent run,
including an incomplete sentinel while it executes. The evaluation decorator
requires at least one turn and rejects any failed/incomplete turn. Ignoring or
mutating a returned result, a later successful turn, and caught cancellation do
not erase failure. Direct diagnostic `run` callers still receive EvalResult.

The shared async `verify_python` helper reuses the existing bounded subprocess
runner. It uses the current interpreter, ignores inherited Python options with
`-E`, enables UTF-8, bounds both output streams to 8192 bytes and defaults to a
five-second deadline. An out-of-workspace receipt is written only after assertions
finish; premature exit zero does not count as verification. Timeout/cancellation
use existing owned-child cleanup. This is not an OS sandbox.

Four existing scenarios have typed rig-accepting helpers and explicit runtime
success checks before independent assertions:

- Counter refactoring: original operations plus independent construction,
  updates and reset behavior across instances.
- Class extension: original method ASTs unchanged; multiplication actually
  updates state for chained, zero and negative operations.
- Scoped rename: name nodes renamed while the other AST is preserved; sampled
  behavior and input immutability verified.
- Multi-file edit: optional email is stored, legacy User behavior remains,
  and app.main supplies a nonempty email during construction. Independent review
  reproduced a mutable-reference false pass (assigning email after construction);
  the observer now snapshots supplied arguments and initial fields. Tests retain
  valid positional and keyword calls while rejecting omitted/empty arguments
  followed by later mutation.

Existing decorated test entrypoints remain. Unrelated scenario bodies were not
rewritten; only annotation fixes were applied where needed for full-file mypy.
The small cases are not complete task, code-style or team-effectiveness proof.

## Validation evidence

- Root initial harness run: 10 failures / 17 passes, including ignored runtime
  failures and missing new verification API (`eval-harness-red.log`).
- Counter original oracle: 3 false-pass regressions reproduced before changes.
- Edit original oracles: 11 false-pass regressions reproduced. Independent review
  added two more false-pass cases for post-construction email mutation.
- Final source selection: **149 passed**, 12.20 seconds, existing Chroma warning.
  `python-eval-contracts-source-final.log`.
- Final fresh installed-wheel selection: **467 passed**, 41.80 seconds on Linux
  / Python 3.12. `python-eval-contracts-wheel-linux.log`.
- Ruff clean across nine files; mypy clean across eight selected runtime/eval/test
  files; scoped diff checks clean. No full-suite or native Windows/macOS claim.
- Offline installed-wheel staging now includes the eval helper and two scenario
  modules plus their offline contracts; live evals are not collected by
  that smoke run and no source production package is copied into staging.

## Compatibility defect exposed by the wheel

The first wheel run had 464 passes / one failure: SDK 3.31.0 rejects empty API keys
when constructing a generic local endpoint. Source SDK 2.21.0 accepted them.
The original failure remains in
`python-eval-contracts-wheel-before-keyless-fix.log`.

After a failing regression was observed, OpenAICompatibleProvider was changed to
pass `api_key or "not-required"` only to the SDK. Saved/configured credentials
remain unchanged; explicit real keys remain intact; SDK environment credentials
are not inherited for the empty-key transport path. Factory validation still
requires real credentials for cloud providers. This does not authenticate against
servers requiring a genuine key. The rebuilt wheel was force-reinstalled before
the successful 467-test run.

## Live exercise of the stronger criteria

Used the already acquired, verified Qwen3-4B-Instruct-2507 Q8_0 artifact and pinned
llama.cpp b11617 Vulkan runtime. No new weights or runtime were downloaded. This
was an explicit local compatible-provider exercise; OpenRouter credentials were
not available. Existing unrelated provider credentials were not used as fallback.

Profile: seed 42; temperature .7, top_p .8, top_k 20, min_p 0, presence penalty 0;
8192 server-context tokens, 6144 agent-input budget, 1024 output cap; one slot;
10 tool rounds and 60 seconds per scenario. Host has 60 GiB RAM / RTX 3090 24 GiB,
not target laptop hardware. Same-server caching and overlapping offline checks
mean timings are observations, not a controlled performance benchmark.

| Scenario | Result | Observed seconds |
|---|---|---:|
| Class extension | Pass | 4.01 |
| Counter refactor | Pass | 4.01 |
| Scoped rename | Fail: tool iteration limit | 5.66 |
| Multi-file edit | Pass | 3.41 |

The rename trajectory first attempted a non-unique replacement, then mixed edit
modes, and finally used shrinking line ranges that removed function structure.
Its saved file is invalid Python. The original failed result and file are retained;
the budget and criteria were not relaxed. Three successful runtime/behavior samples
do not establish general model reliability.

Full traces, tool outcomes, final files, memory scope and process exit status are
in `local-model-16gb-probe/qwen3-4b-python-quality-vulkan.json`; logs use the same
prefix. The owned server (PID 2760128) exited zero and was confirmed absent.

## Documentation and remaining work

Updated evals/README.md, docs/evals/README.md, docs/providers.md, CHANGELOG.md,
FEATURE_TODO.md and TODOS.md. No Git staging, commits or publication.

The observed rename failure provides concrete evidence for further edit-error
recovery work. Broader real-repository Python/style/type/test outcomes, DevOps
workflows, live team coordination, accurate usage/cost coverage and live OpenRouter
evaluation remain open. The older local-model RAM/CPU/GPU observations remain
separate evidence; this turn does not qualify or ship a local default.
