# Windows subagent question failure — 2026-11-08

The [Windows Python 3.11 installed-wheel job](https://github.com/mlg151/henchman-ai/actions/runs/42514229554/job/128833925441)
for commit `f59f51a` failed one test: the non-durable
`test_child_question_and_parent_answer_use_real_queued_messages` returned from
the parent run without setting its `answered` flag. The job reported **5,976
passed, 242 skipped and one failed**. The assertion did not record child state,
event output or a timeout, so its cause cannot be established from that log.

A clean Linux checkout of that same commit passed 80 repetitions of the test
in one pytest process with separate temporary workspaces: 40 each with
process-local and durable operation persistence. A
separate two-case probe delayed the parent launch tool's return by 50 ms, so the
child could run while the parent launch was still active; both persistence modes
passed. These checks do not reproduce Windows scheduling or the full wheel job,
and they do not prove the Windows failure was a timing issue. No deadline or
runtime behavior was changed based on this result.

The test now includes bounded synthetic child state, completion status and
events in the failed assertion to make a recurrence diagnosable. The full
Windows job and release gate remain unresolved until a new exact-head run
passes and any recurring failure is explained.

The original job log is retained locally under
`ci-f59f51a/windows-311.log` in the release-qualification cache; its SHA-256 is
`de72ccb85cd5f53f708c210b6e04d3d17e2ef84e8a6a5b49bbcc1081ab99c210`.
The exact [repeat](../../evals/subagent_question_ci_f59/question_repeat_executed.txt)
and [delay](../../evals/subagent_question_ci_f59/question_delay_executed.txt)
probe files are archived separately. Their SHA-256 values are
`7642880d4848ce2bcd4a308fe994923189e43fb683fbee0a938b4c71f4367e5b`
and `20a1aa627b6e5dc503fad516ec7fa6c3f6a008340bbf0effb833d8862eff7030`,
respectively. The probes used private HOME and temporary directories and made no
model calls.
