# Python development goal: evidence and next work

Follow-up: the unrestricted environment now passes all 12 real-tool coding-loop
cases and the fresh installed-wheel smoke (82 checks). See the updated platform
checkpoint; the sandbox-blocked statements below describe the earlier run.
The existing live eval harness now uses explicit shared provider construction and
the bounded headless loop, with timeout/terminal failure regressions. The new
Python reuse scenario independently rejects copied helper implementations.

The expanded goal adds Python developer focus, organized idiomatic code, removal
of smells, reuse-before-implementation, DevOps, and whole-team leadership. All remain
outcome requirements; a prompt or a registered tool alone is not completion proof.

## Current discoveries and repairs

- Existing registered file_overview, symbol_trace, and pattern_search tools were
  absent from every default specialist allowlist. Shared discovery category now
  exposes them in default roles, with actual AgentPool runtime tests and unchanged
  custom allowlists.
- Structural inheritance search lowercased class identifiers and missed real
  implementations. Regression now preserves identifier case and finds candidates.
- Generated role prompts now carry a shared Python workflow: inspect candidate
  implementations/callers/tests, record reuse decisions, assign ownership, verify
  integrated results, and distinguish absent/failed checks from successful evidence.
  These instructions need behavioral evaluation before compliance can be claimed.
- git_ops show combined ref, separator, and file path in one argv element. A real
  temporary-repository regression failed before the fix, now checks success and
  requested diff while excluding the unrelated file. 28 Git tool tests passed.
- Pytest path='--version' returned success without tests; unsupported lint selector
  pyright returned success without running checks. Runtime validation now rejects
  invalid selections and option-like targets. Arguments use an explicit separator.
- Pytest now uses an explicitly loaded, independent completed-session reporter.
  A zero process exit alone is insufficient: execution needs matching session mode
  and a passed test call. Inherited collect-only options, missing evidence, and all
  skipped tests fail verification. Explicit collection is labelled separately.
  Built-in JUnit was evaluated first: collection of two tests produced zero XML
  cases, and supplying our own --junitxml would replace the project's configured
  report destination. A real subprocess regression verifies project JUnit artifacts
  survive alongside the independent report.
- Pytest/lint share bounded UTF-8 subprocess capture and interrupted-child cleanup.
  Review regressions cover inherited collection falsely succeeding and cancellation
  of the cleanup task causing an infinite retry loop. Both are resolved.

## Final local verification

- Combined Python development suite: 301 passed on Linux/Python 3.14.4 in 37.53s.
  Scope: pytest/lint/integrity/reporter, presets/prompts/pool, pattern search,
  file overview/symbol tracing, Git operations, installed-wheel staging helper.
  One upstream Chroma asyncio deprecation warning; no test failures.
- Ruff clean across touched source/tests; mypy clean across eight source modules;
  scoped git diff --check clean.
- Final wheel rebuilt successfully; archive inspection confirms inclusion of the
  independent pytest reporter and shared subprocess helper. This is build evidence,
  not a fresh-install or native macOS/Windows run.
- Native-platform slice has its separate 158-pass result in the portability
  checkpoint. Counts overlap; do not add them into an aggregate total.
- Installed-wheel CI stages the verification-integrity suite. Hosted CI and the
  ten real file-edit coding-loop cases remain unverified due to the previously
  documented sandbox thread-dispatch hang. No project commit or push performed.

## Included local model requirement

User baseline: 8 GB RAM laptop; CPU-only is the stated starting assumption. Evaluate
actual total memory and Python-tool usefulness before choosing a bundled default.
Preserve editor/OS headroom and existing OpenRouter/provider portability. This is
not fulfilled by documenting an externally installed server. Research and next
integration steps are tracked in `2026-10-14-local-default-model.md`.

## Reuse the existing smell/duplicate implementation

Canonical current engine: scripts/smell_detector/scanner.py::scan_repository,
scripts/smell_detector/detectors/duplicates.py::DuplicateCodeDetector.detect_repo,
models.py, formatter.py and per-file detectors. It is not shipped in wheels because
only src/henchman is packaged. Do not create a parallel detector implementation.

Before exposing it as a runtime tool:

1. Establish behavioral fixtures for duplicate/similar functions, nonduplicates,
   nesting/size issues, valid idioms, syntax errors, and unavailable optional tools.
2. Move canonical analysis into the runtime package with compatibility imports for
   existing scripts; keep one implementation and preserve script consumers.
3. Bound traversal and report excluded/failed files. Current excludes are string
   glob checks after rglob, and root .venv paths need a dedicated regression.
4. Give findings inspectable file/symbol/line locations and heuristic limitations.
   Identifier-normalized AST similarity is a reuse candidate, not proof of semantic
   equivalence or a guarantee that code is smell-free.
5. Register a real builtin import_path, use shared discovery truth, and grant it to
   appropriate scoped roles. Verify execution through installed wheel and registry.
6. Evaluate an actual task where an existing implementation should be reused; compare
   evidence, changes, behavior tests, and maintainability before claiming success.

## DevOps and leadership gaps to retain

- Project verification currently uses Henchman's sys.executable with no project
  interpreter/cwd selection. Ordinary isolated installations may lack project
  pytest/ruff/mypy even when the project has them. Explicit project-environment
  resolution and reporting needs a focused implementation; no silent fallback.
- Formatter, pip, and Git subprocess timeout cleanup still need verification;
  PythonExec can hang if SIGTERM is ignored. Reuse the bounded subprocess helper
  from the current pytest/lint slice after its behavior is verified.
- Leader docs/preset say read-only while setup_tech_lead passes the full parent
  registry. Clarify intended permissions and enforce the chosen contract; prompt
  text alone does not constrain tools.
- Existing role prompts repeat large fragments. Refactor only with behavior-preserving
  prompt assembly coverage; do not mix unrelated cleanup into current tool repairs.
- Team-level acceptance remains open: ownership, dependent and parallel work,
  independent review, integration, failed/blocked handoffs, and authoritative
  verification evidence. Offline runtime mechanics need model-driven task evals.
- Keep provider/OS portability and OpenRouter emphasis from the original goal.
  Native hosted CI and ten real read/edit/test workflow cases remain unverified as
  recorded in the platform checkpoint. No benchmark or production-leading claim.
