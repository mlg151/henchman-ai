# Python quality tooling

Previous goal turn: verified progress (real question channels, interruption,
installed108-check pass, additional local-model task failures). Goal remains active.

## Reuse and design

The existing repository scripts/smell_detector package supplies models and three
useful AST detectors, but was not packaged for the agent. Promote these to
henchman.analysis.smells, retaining script import compatibility. Fix false clone
matches caused by erased identifiers/literals, quadratic comparison/output, flat
elif nesting, missing modern constructs and unqualified symbols.

Expose bounded review through the existing python_ast(action="quality") surface;
keep default symbols mode. Parse one source at a time, retain fingerprints and
first locations only, prune dependencies before traversal, and report scope/errors
and limits as JSON. A successful scan does not mean smell-free code or semantic
interchangeability. No source is imported/executed and no new dependency is needed.

## Work and evidence

- Baseline existing tools:115passed. Root quality regressions:12failed before
  implementation; then57passed across quality, AST and AST helpers.
- Canonical detectors:18passed after TDD, including1,200elif branches. Their
  recursive fingerprint serialization can still fail on pathological ASTs;
  scanner reports those RecursionErrors explicitly instead of claiming success.
- Resource/cancellation tests:5passed for file/totalbyte/entry limits, symlink
  scope and stopping after the current source. Registry/discovery test proves
  actual ToolManager tool_search exposes quality and registered execution works.
- Review found no concrete scanner defect in coverage, budget or cancellation
  semantics. Root and detector Ruff/mypy checks passed at this stage; final gates
  below will supersede intermediate results.
- Real scan of src/henchman/cli:67files,730306sourcebytes,38candidates, no errors
  or truncation,1.478seconds measured after imports on this host. This is a bounded
  functional probe, not whole-application memory or8GBlaptop acceptance evidence.
  Artifact:python-quality-cli-report.json.
- Legacy command python -m scripts.smell_detector src/henchman/analysis
  --skip-external --format json succeeded; legacy-smell-compatibility.json.
- Symbol signature accuracy follow-up: ast.unparse(node.args) now preserves
  positional-only/keyword-only/variadic/default parameters and annotations;
  34 helper tests pass, including the existing decorated-method format.
- Installed smoke now includes quality and resource-limit tests.
  Windows/macOS hosted execution remains open.

## Final source verification

- Focused combined suite: 194 passed in 3.13 seconds; existing Chroma asyncio
  deprecation warning only. Log: python-quality-final-tests.log.
- Ruff passed for changed source and tests; mypy passed for 12 source files.
- Scoped git diff --check passed.
- Built wheel and force-reinstalled it into the isolated Python 3.12 environment
  successfully. Logs: python-quality-wheel-build.log and
  python-quality-wheel-reinstall.log.
- Installed Linux wheel smoke passed: 126 tests in 27.34 seconds, both CLI
  aliases, and local RAG operations. The runner asserted the installed package
  origin and executed staged tests outside the checkout. Log:
  python-quality-wheel-linux-final.log. This is Linux runtime verification,
  not native macOS/Windows, live-provider quality, or physical 8GB acceptance.

## Open outcomes

This adds bounded syntax-clone/long-method/nesting candidates only. Semantic reuse,
behavior-preserving refactoring, richer code smells, real model task quality,
DevOps/team leadership, local default selection and physical8GB/nativeOS evidence
remain goal requirements. No staging, commit, push or publication is planned.
