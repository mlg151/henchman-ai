# Next local-model behavioral gate

Read-only inspection, 2026-10-14. No model calls, downloads, production/eval edits
or test executions. Target remains 16 GB RAM with CPU operation and optional GPU.
Two arithmetic/reuse passes would justify broader evaluation, not default-model
qualification. Canonical guidance: [evals/README.md](../evals/README.md), linked by
[docs/evals/README.md](../docs/evals/README.md).

## Four reusable scenarios

The exact pytest node IDs below are also the module-level callable names. Keep
their current prompts and assertions for comparable baseline results. All four
call `EvalTestRig.run` with its defaults: **10 tool rounds**, whole-turn timeout
from `EVAL_TIMEOUT` or **60 seconds**. Independent child Python checks have a
**5-second timeout**. Three are `USUALLY_PASSES`, requiring `RUN_ALL_EVALS=1`;
`test_add_method_to_class` is `ALWAYS_PASSES`.

| Order / exact node ID | Existing task and unchanged oracle | What a pass actually establishes |
|---|---|---|
| 1. `evals/test_edit_precision.py::test_add_method_to_class` | Add stateful `Calculator.multiply`. A subsequently created `test_calc.py` checks existing add/subtract/clear behavior and `add(4); multiply(3) == 12`; child exits 0. | One class extension preserves sampled behavior. Despite the prompt, there is no assertion that existing method bodies remain unchanged. It does not check `result` after multiplication or multiplication by zero/negative values. |
| 2. `evals/test_coding_tasks.py::test_refactor_to_class` | Replace module-global counter functions with `Counter`. A subsequently created `test_counter.py` checks initial 0, increments 1/2, decrement 1, reset 0; child exits 0. | Small state refactoring works for one instance. No two-instance independence check or assertion that global state was removed; a class wrapping globals could pass. Not a general Python-idiom quality measure. |
| 3. `evals/test_edit_precision.py::test_rename_variable_consistently` | Rename `tmp` to `result` in three functions. Assert no `tmp` substring, at least six `result` substrings, then execute doubling, positive-filtering and reversed-copy examples. | Consistent source renaming with three behavioral samples. Counts are textual, not scoped AST bindings; preservation, input immutability and generality are not comprehensively checked. |
| 4. `evals/test_edit_precision.py::test_multi_file_edit` | Add optional `User.email` and update caller. Assert `email` appears in models, `email` or `@` appears in app, then execute `app.py` successfully. | Weak multi-file smoke only: comments satisfy the substring checks, and the unchanged app already exits 0. No assertion proves optional constructor compatibility, stored email or actual caller argument. Do not count this unchanged oracle as coordination correctness. |

These tasks need ordinary file inspection/editing (`read_file`, `edit_file` or
`write_file`); `ls`/`glob`/`grep` can support navigation. The rig supplies these plus
`shell`, `web_fetch`, and `ask_user`, auto-approves tools, and uses a temporary CWD
that is **not** an OS sandbox. The four assertions do not require a particular
tool, successful inspection before editing, or model-initiated tests. Their
independent checks use literal `python` from PATH, not `sys.executable`.

## Concrete gaps before using these as acceptance gates

All four discard the returned `EvalResult`. A model can edit successfully and
then time out, hit its iteration limit or encounter a provider error while the
pytest scenario still passes. Require runtime completion as a separate result
alongside the unchanged behavioral assertions; never turn partial runtime failure
into a completed-task claim. Preserve traces and edited files before cleanup.

The checks generally create verification scripts *after* the agent turn. They are
independent execution checks, but do not show that the model saw a failing test,
interpreted it, repaired code and reran it. There is **no existing live eval in
`evals/` that requires that recovery sequence**. The stronger reuse scenario,
`evals/test_python_reuse.py::run_python_reuse_scenario`, provides the existing
pattern to extend: immutable fixtures, successful edit evidence, post-edit pytest
tool evidence and `verify_python_reuse` independent execution evidence. It uses
12 rounds / 300 seconds plus an independent 30-second pytest check; even that
scenario does not require an observed initial failed test.

There is also no live team-coordination scenario here. `EvalTestRig.setup` creates
one `Agent`, and `run` provides the headless loop with an agent/registry only, not
an orchestrator. Its tools omit `delegate_task`. Tool-selection evals for grep/glob
only assert a tool log exists, which need not represent successful navigation.
Multi-file editing is useful, but cannot establish specialist coordination.

## Smallest next sequence

1. Finish the existing arithmetic/reuse CPU probe with unchanged oracles. If it
   fails, preserve the failure and diagnose before escalating to a broader score.
2. Reuse the four existing scenarios in order, retaining their assertions and
   reporting the fourth only as a weak smoke. Set a named CPU budget explicitly
   (suggested 300 seconds per turn, still 10 rounds); keep the original 60-second
   configuration distinguishable. Record runtime status, independent assertions,
   elapsed time, truncation, tool evidence and model/runtime/settings pins.
3. Before that run, expose scenario bodies as explicit rig-accepting helpers using
   the already established `run_python_reuse_scenario(rig)` pattern, with existing
   pytest wrappers calling them. This is a narrow future harness change, not done
   here. Current `eval_test` wrappers construct `EvalTestRig()` internally and do
   not expose `__wrapped__`; they cannot accept the current probe's 6144-token
   agent budget or pinned provider sampling. Do not silently replace the explicit
   context policy for the 8192-token local server or introspect function closures.
4. Strengthen existing oracles additively before treating passes as qualification:
   runtime success, independent Counter instances, actual optional email/caller
   behavior, and an observed failure→repair→retest extension of the current reuse
   scenario. Preserve the original diagnostic outcomes and reject known bad
   implementations in offline oracle tests. Reuse
   `tests/testing/test_eval_helpers.py` for harness contracts.
5. Repeat the resulting gate with recorded seeds and CPU/GPU configurations
   separately. Continue whole-application 16 GB accounting and later real
   repository/team tasks; these small single-agent scenarios alone cannot prove
   an industry-leading or included-default claim.
