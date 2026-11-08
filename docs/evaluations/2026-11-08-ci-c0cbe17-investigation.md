# Follow-up CI investigation at `c0cbe17`

In [CI run 42496659440](https://github.com/mlg151/henchman-ai/actions/runs/42496659440),
the Windows/Python 3.12 installed-wheel job passed with **5,965 passed and
236 skipped**. Its log records 454 installed package files matching the wheel;
the retained log SHA-256 is
`89b9a036e89605593093af4695237fb404f683e4bfa293e52cfd46dd8714f4be`.
This job includes the decision-review export tests that failed in the previous
run. Other jobs were still active when this note was written.

The Windows/Python 3.11 wheel job failed two parameterizations of
`test_terminal_downgrade_cannot_overwrite_a_newer_repair_owner`: **2 failed,
5,963 passed and 236 skipped**. Neither expected exception was raised. The
log does not state the returned repair outcome or whether the intended
replacement was reached, so the cause is not established. The log SHA-256 is
`00c8f0cfe757cbd385b60fa044610d5ed37bdc5d9f3b1d72f17455792f8256bd`.
The prior Anthropic discovery failure did not recur in this job.

The test's injected clock controls its deadline race, but it also set a
one-second real event-loop timeout around native filesystem work. A follow-up
gives that work 120 seconds while advancing the injected clock beyond the same
deadline, and reports the actual outcome and replacement count if the expected
exception does not occur. The two affected cases and four adjacent terminal
control cases passed locally on Python 3.11 and 3.12. This change preserves the
ownership assertions but has not yet been verified in a new Windows run. Both
native logs are retained under `ci-c0cbe17-42496659440` in the local
qualification cache.
