# CI concurrent subagent timeout — 2026-11-08

The [CI run on `4ba6f71`](https://github.com/mlg151/henchman-ai/actions/runs/42504651298)
reported a failure in the Linux Python 3.11 source job:
`test_concurrent_subagents_reactively_resume_primary_and_preserve_transcript`
timed out after three seconds. The job reported **12,670 passed, 91 skipped,
one failed**. The run was still in progress when this report was written. The
retained job log SHA-256 is
`5513b86fc67e692d9837841c3186f84997afa41f4c5a0ba82b6c1b6b50286689`.

The traceback shows the parent waiting for a subagent notification and cleanup
after timeout. It does not show whether the second child was slow, was never
started, or failed for another reason. A local controlled experiment delayed
the second child by 3.2 seconds while keeping the existing two-child barrier:
the original three-second test timed out. This establishes that slow startup
can produce the same class of failure, not that it caused this CI failure.

The test now retains the two-child concurrency, notification, transcript and
completion assertions, adds ordinary and delayed-start cases, and uses a
15-second outer deadline. On timeout it captures child states, errors,
outputs, parent call count and partial synthetic transcript before cancelling
and joining the worker. Python 3.11 passed **30 related agent tests**; Python
3.12 passed both concurrent cases. Ruff passed. This changes a test fixture,
not the production runtime or its deadlines. A later native/full source run
is still needed to evaluate the change.
