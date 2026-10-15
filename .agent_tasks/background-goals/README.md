# Background execution and persistent goals

User outcome: allow shell redirects, execute shell/Python jobs in background by default, track multiple jobs concurrently, accept user interaction during agent work, and keep pursuing `/goal` across turns until completion or pause (confirmed).

Design: reuse project-local TaskService for jobs and existing task_get/list/output/stop tools. Return launch receipts rather than claiming process success. Retain explicit background=False for synchronous callers. Persist goals in session metadata, with generation IDs and a real completion tool. Both interactive frontends serialize agent turns, accept queued user messages during work, and prioritize them over automatic goal continuation. Goal controls can pause continuation during an active turn. Keep terminal prompts exclusive for questions/approval.

Implementation: execution worker owns TaskService/tool changes; redirect worker owns validators; goal worker owns goal service, command, tool and registration. Root owns UI integration, tool scopes, docs and joint validation. Existing dirty changes are preserved.

Verification: failing redirect/background/lifecycle/goal/UI regressions first, then focused pytest, Ruff and Mypy. Include real mixed subprocess concurrency, output/failure/timeouts/cancellation, serialized UI input and goal completion/pause/resume.

Status: redirect slice passed 296 focused tests. Execution and goal implementations in progress. UI tests next.

## Implementation and review

Implemented redirect support, shared background task lifetimes and IDs, session goals and structured completion, default/custom agent companion tool scopes, canonical discovery entries, and serialized responsive REPL/Textual input. Existing unrelated edits remain untouched.

Review caught and fixed: session mutations during active classic turns, error-event goal retry loops, timeout-log failures bypassing cleanup, and descendants escaping tracking on parent exit. An independent reviewer reran those four regressions successfully. Classic asynchronous output uses prompt-toolkit stdout routing and preserves typed drafts. Textual queued messages also recover after provider exceptions.

## Verification

- Execution worker: 300 focused tests, Ruff and Mypy passed, including 14 real subprocess regressions.
- Root integration: 177 Textual/goal/scopes/discovery/docs tests passed; 60 additional classic/Textual interaction tests passed.
- Expanded root execution run: 451 tests passed and two old synchronous-formatting expectations failed. Those tests now explicitly request foreground execution; all eight registry-formatting tests pass after the correction.
- Final classic output-rendering seam: 62 tests, Ruff and Mypy passed.
- Canonical background capability matrix: 33 discovery/help/docs tests passed.
- Root combined Ruff and Mypy (14 production modules) passed. Final small Textual queue-recovery and matrix checks are recorded in the conversation.

## Runtime boundaries

Background jobs are tied to the application's event loop, not detached daemons. POSIX jobs own their process groups; Windows cleanup currently targets the direct subprocess. Default background launches skip synchronous automatic formatting and explicitly tell the agent to format changed Python after completion; background=False retains existing automatic formatting. Goal completion requires the current revision and a verification summary and conservatively rejects completion while any project job is running; users can override with /goal complete. Agent completion remains a reported verification summary, not independent semantic proof.

Status: Complete. Final 15 Textual queue/goal and discovery tests passed; Ruff and Mypy passed on the final affected modules. Diff whitespace checks passed.
