# CI concurrent subagent timeout — 2026-11-08

The [CI run on `4ba6f71`](https://github.com/mlg151/henchman-ai/actions/runs/42504651298)
reported a failure in the Linux Python 3.11 source job:
`test_concurrent_subagents_reactively_resume_primary_and_preserve_transcript`
timed out after three seconds. The job reported **12,670 passed, 91 skipped,
one failed**. The run finished with **18 of 20 jobs passing**; this source job
and the aggregate gate failed. The
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

A clean wheel built from `536fcf7`, imported from isolated Python 3.12.13
`site-packages`, passed all **30 related agent tests**. The wheel SHA-256 is
`cd2c0887957719d9ea8d8c9430e74edec2385dc6327236256e1f247090afddd9` and its
test log SHA-256 is
`b934e22dc612e4d630f117643ec7849d5c70e352476b230263d0876432020d78`.
Separately, an isolated test copy with its outer deadline forced to 0.01 seconds
failed as intended and printed the child states and partial transcript before
cleanup; that log SHA-256 is
`708695da23a1bce3be08ce4233323cf80c510ccb2aa536608d62764d6e44c41b`.
The changed test copy was restored afterward. These development-wheel results
do not qualify a release artifact.

Five separate Python 3.11 pytest processes subsequently passed the ordinary
concurrent case; the combined log SHA-256 is
`a4c92fcf545c286d75f770ad40be3a1977a0c4a5cf45b6d6911335389bef3a76`.
Two earlier attempts to repeat selected nodes in one pytest process executed
only the two distinct parameter cases, so they are not counted as repeated
trials. Their respective log SHA-256 values are
`e7c31dc78759ef7d74503bb21c3dc7c069ff6b805936020aac642dbbdf79cc03` and
`f598b76ba24dc91179e08ac7fb4d40c0ed9808d6e755343978dc63ccc49f0847`.
These short local repetitions do not reproduce the full CI environment or prove
the intermittent failure cannot recur.

All 12 installed-wheel jobs in the original `4ba6f71` run later passed across
Linux, macOS and Windows. The Windows 3.11 job, which had failed repair-owner
tests on the earlier `c0cbe17` run, reported **5,965 passed, 242 skipped**;
its log SHA-256 is
`171de81047cf5f0121cc5ae81e1ed171129282d7b944ddb59d97259556144031`.
The Python 3.12 source job passed **12,671 tests, 91 skipped**, with 91.26%
coverage. Its log SHA-256 is
`59a8ad04af125e25c77f13a7945a50a745e4ea2c938ba5f3b192b42f5e529912`.
