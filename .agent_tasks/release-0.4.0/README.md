# Production PyPI release 0.4.0

User authorized running the tests, building 0.4.0 and publishing to production PyPI. TestPyPI is explicitly excluded. Release current workspace contents; preserve existing edits. No GitHub release workflow is invoked because its existing workflow includes TestPyPI.

Version: pyproject.toml and runtime version both 0.4.0. Production PyPI version endpoint initially returned 404. Production repository credentials are configured in ~/.pypirc; secret values are never logged.

Initial checks: uv lock --check, full Ruff lint and full Mypy (325 modules) passed. MkDocs builds with existing link warnings. Full pytest (8,209 collected tests, required 90% coverage) is running; integration fixture failures are being diagnosed before publication. Ruff format check reports existing drift in 411 files; avoid unrelated wholesale formatting. Bandit report is being triaged for real issues.

Full logs, audit output, build distributions and installation environments remain in this folder, which is excluded from distributions.

Status: Published henchman-ai 0.4.0 directly to production PyPI. Both public downloads match the tested artifact hashes.

## Repairs and build candidate

Resolved legacy fixtures for background-default execution, scoped agent registries, provider contracts, current event signatures and formatting expectations. Fixed real tar extraction vulnerability by rejecting links/devices/FIFOs before extraction, with five regressions; nonsecurity MD5 operations now explicitly declare their purpose. Production Ruff and Mypy (325 modules) pass, and Bandit has zero HIGH findings (8 MEDIUM and 54 LOW remain, including intended shell execution/static-query/blocked-address patterns).

Candidate wheel and sdist pass Twine checks and exact archive-member checks. They exclude scratch trees, backups, dotenv/credential files and coverage data; wheel includes goals, task service and TUI resources. Clean sdist Python 3.11 install passes CLI aliases, readiness, local Chroma operations, redirects, four background jobs and structured goal completion. Wheel Python 3.11/3.14 workflow suites are running.

Fresh full pytest with required 90% coverage started after repairs, using a separate coverage database. Previous diagnostic full run continues to expose any remaining failures.

## Full diagnostic sweep and final validation

Initial complete run: 8,104 passed, 98 failed, 7 skipped; 92.98% branch-inclusive coverage. Failures were tracked and repaired through targeted runs: stale provider/UI fixture contracts, actor-scoped registry expectations, foreground requirements for verification/artifact commands, and exact expected formatter output. An empty-venv fixture now uses working POSIX interpreter symlinks, verified on Python 3.11 and 3.14.

Two subprocess output failures were pytest-cov instrumentation errors (child interpreters did not discover the project's branch configuration). Explicit coverage config passes both exact-output tests; pytest addopts now pins pyproject.toml so the standard command also propagates the same configuration. The current full rerun uses the identical explicit absolute configuration and is green so far. An earlier partial rerun was interrupted when further diagnostic failures became known; its partial logs/data are preserved under interrupted/.

Installed wheel suites each completed 1,578 cases. The three failing cases per interpreter were repaired fixtures; all four affected cases (including both late-command variants) passed on both interpreters after restaging. The final wheel is byte-identical to the tested candidate, and its 330 package members match current source. Final sdist runtime smoke passed after reinstall. Rebuild sdist after final test-config/changelog adjustment before upload.

## Final result — published

Release: https://pypi.org/project/henchman-ai/0.4.0/

- Complete final suite: **8,207 passed, 7 skipped, 0 failed** in 696.52 seconds; **93.23%** branch-inclusive coverage. See pytest-final.log, pytest-final.xml, coverage-final.json and test-summary.json.
- Full Ruff lint and production Mypy (325 modules) pass; lockfile and whitespace checks pass.
- Wheel tested on Python 3.11 and 3.14, including CLI aliases, package origin, local vector operations and 1,578 offline workflow cases. Corrected fixture cases were rerun successfully on both interpreters. Final wheel is byte-identical to the tested candidate.
- Final source archive reinstalled on Python 3.11 and passed CLI aliases, readiness, local Chroma, redirects, four tracked jobs and goal completion.
- Both final distributions pass Twine and archive-member checks, exclude private/scratch/backup files, and contain required runtime modules/resources.
- Uploaded only the exact checked wheel and sdist using the production endpoint. No TestPyPI publication or GitHub release workflow was invoked.
- Confirmed the public production project/version and downloaded both uploaded files; their SHA-256 values match manifest.json. See pypi-verification.json and published/. The version-specific JSON endpoint briefly retained its earlier negative cache; the production project JSON and human release page correctly expose 0.4.0.

Nonblocking existing checks: Ruff formatting check initially reports drift in 411 files; no wholesale formatting rewrite was performed. Bandit final report has no HIGH findings, with 8 MEDIUM and 54 LOW findings retained for inspection. Documentation builds with existing link warnings. Strict Mypy checks on some old test fixtures report preexisting diagnostics; the required production-source type check passes.

The workspace's preexisting edits are preserved. No Git commit, push, tag, or GitHub release was needed for the requested direct PyPI publication.
