# Behavioral evaluations

The maintained evaluation guide lives in [`evals/README.md`](../../evals/README.md),
alongside the real-provider scenarios and shared test rig. It documents provider
selection, local endpoints, timeout and iteration limits, and evidence semantics.

The Python reuse scenario in
[`evals/test_python_reuse.py`](../../evals/test_python_reuse.py) checks inspection
before editing, unchanged helper/test fixtures, actual calls to an existing helper,
and independent pytest execution. Runtime completion alone does not satisfy those
behavioral assertions.

Use offline harness contracts under `tests/testing/test_eval_helpers.py` to verify
the runner without model calls. Live scenarios require an explicitly configured
provider and must not be described as passing until they actually run successfully.

The shared decorator also rejects ignored runtime failures and scenarios with no
agent turn. Counter, class-extension, rename and multi-file scenarios have
independent behavioral checks and offline tests that reject known false passes.
See [runtime completion and Python checks](../../evals/README.md#runtime-completion-and-independent-python-checks)
for reusable scenario entrypoints, process limits and evidence boundaries.

Use the opt-in [engineer evaluation profile](../../evals/README.md#evaluation-profiles)
to exercise the production engineer prompt and available tool scope. The default
basic profile remains a minimal harness. Report the chosen profile and effective
budgets when comparing results; neither profile establishes full-team quality.

The explicit [production team evaluation](../../evals/README.md#production-team-evaluation)
uses the real orchestrator and attributed tool events. Its Python reuse/CLI task
has separate workflow, correctness, lint, formatting and type checks, with a
durable report outside workspace cleanup. Scripted contracts validate these
criteria; live model results must be reported separately.
