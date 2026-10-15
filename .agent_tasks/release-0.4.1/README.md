# 0.4.1 PR review and integration

Status: PRs #5, #6, and #7 reviewed, fixed, and merged into `0.4.1`. PR #8 remains the draft release PR into main. Original checkout and existing unrelated artifacts are preserved.

Review findings and fixes:

- #5: repaired the new RFC link in the symlinked rendered changelog; 101 focused tests and rendered MkDocs pass.
- #6: bounded Black-expanded output so valid snippets cannot become oversized Windows process arguments; regressions failed before the fix, and 166 focused checks pass.
- #7: removed mutation-lock blocking from dynamic coordination and preserved execution budgets across notifications; five regression cases reproduced failures and pass after the fixes, with 93 focused checks passing.
- Enabled staging CI triggers with a failing-then-passing regression. Resolved changelog/roadmap conflicts retaining all features and the original scope boundaries.

Final merged tree: 139 focused integration tests pass; full Ruff passes; wheel/sdist builds and Twine validation pass. Full Mypy and initial broad integration tests are running; hosted final-tree CI is queued/running. Logs remain local under this task directory or the separate review worktree's task directory. Release tracking docs and draft PR #8 are updated to reflect integrated features; versioning/publication remain outstanding release work.
