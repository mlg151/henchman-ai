# Typed acceptance observations

Previous goal milestone: response/action completion semantics, 488 focused source
and 247 installed Linux wheel checks. Full goal remains active; 8 GB CPU laptop
is the target, not the test host. No useful included local default selected yet.

## Implemented slice

Existing verify_plan_execution/PlanExecutionService now accept immutable check
specifications at creation and run them through a verify action. Kinds:
file_exists, literal file_contains, baseline-backed file_changed, argv command,
and pytest with actual completed-session execution evidence. Legacy complete is
reported checklist progress only. No report claims whole-task correctness or
user-authorized requirements; task_verified remains false.

Reports record exact checks, spec digest, timestamps, per-check observations,
file fingerprints where applicable, output truncation and pytest counts. Status
and confirmation requests expose recorded checks. Reports are historical; edits
require rerunning verification. The tool is EXECUTE and existing registry plan
mode and confirmation policies apply. Commands run with literal argv and project
cwd, not a sandbox.

Limits: 20 sequential checks; 1 MiB content/report reads; 64 KiB stdout/stderr
prefixes drained concurrently; command argv64/16KiB; timeout1..300 seconds.
These do not cap subprocess RAM or guarantee hardware suitability. POSIX
interrupted subprocess cleanup includes owned process groups; Windows stops only
the direct child. Successful background descendants are not a supported sandbox.

Plan persistence now uses bounded16MiB index reads/writes, atomic same-directory
replacement and a shared native FileLock extracted from the existing RAG lock.
RAG compatibility preserved; utility lock does not import RAG/Chroma. Mutations
reload under lock. Verification releases lock during checks, preserves concurrent
step updates and rejects superseded runs. Cancellation clears previous success
and preserves cancellation even if another run has superseded its report.
Corrupt plan data fails locally without disabling all builtin registration.

PytestEvidence.from_dict shares existing validation with bounded report parsing;
the acceptance engine reads the artifact only once. Python3.11/3.12 symlink-cycle
RuntimeError is normalized to a failed check; newer OSError also fails normally.

## Review / verification

Initial root integration cases failed before implementation: missing checks API,
stale-service record loss, corrupt state silently reset. Engine, bounded runner,
and shared lock workers used focused regression tests. Independent review found
superseded cancellation masking and eager corrupt-store constructor failure;
both fixed with regressions. Review found no further blocking engine/runner issue.

Final focused source suite: 182 passed in 21.62 seconds (Python3.14).
Fresh installed Linux wheel: 329 passed in 32.89 seconds (Python3.12),
plus both CLI aliases and local RAG operations. Runner asserted installed
package origin outside the checkout. All process handles finished successfully.
Logs: acceptance-source-final.log and acceptance-wheel-linux.log.
Ruff clean for touched runtime/test files. Mypy7 runtime modules clean; worker
engine/reporter four-file mypy clean after the final portability correction.
Scoped diff checks clean. This is not a full repository suite or native OS matrix.
Docs: docs/tools.md, CHANGELOG.md, FEATURE_TODO.md, TODOS.md, optional backwards-
compatible plan_record schema fields. Installed-wheel staging includes new
acceptance, persistence, bounded subprocess, shared lock and report-parser tests.

## Still open

Whole-task correctness/requirements adequacy, real-model Python task quality,
team/DevOps outcomes, local model selection and measured8GB CPU experience,
native Windows/macOS and hosted CI verification remain required. No staging,
commit, push or publication. Existing extensive dirty tree preserved.
