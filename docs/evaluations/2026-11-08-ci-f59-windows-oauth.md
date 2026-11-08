# Windows OAuth launcher fixture failure — 2026-11-08

The [Windows Python 3.12 installed-wheel job](https://github.com/mlg151/henchman-ai/actions/runs/42514229554/job/128833925414)
for `f59f51a` failed the successful synthetic browser-launch case, reporting
that the launcher failed or exceeded its deadline after URL handoff. The job
reported **5,976 passed, 242 skipped and one failed**. Its sanitized error does
not distinguish a deadline from another launcher failure, so the exact cause
is unproven.

The success fixture used a **0.3-second** post-handoff deadline, while the
production launcher uses 10 seconds. In a separate Linux control, a synthetic
child that accepted the URL and exited after 0.65 seconds failed with the same
sanitized error under that fixture deadline. This shows a possible failure
mechanism, not the observed Windows cause. The success test now allows three
seconds and includes that delayed-success case. Timeout, cancellation and
cleanup cases retain the short fixture deadlines; production code and its
deadline are unchanged. Native Windows verification of the change is pending.

The job log is retained locally as `ci-f59f51a/windows-312.log` in the
release-qualification cache; its SHA-256 is
`bd66f4ef2db0c4ed374cf50150f696f3c02924012fea8661552a9a9139e2ba02`.
The control used an owned synthetic subprocess and did not open a browser or
contact an OAuth server.
