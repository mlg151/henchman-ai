# Staged paired comparison v1 — invalid guard

This cohort was stopped and is not a valid comparison. Its execution guard
treated the runtime's primary `tech_lead` actor as a child. The first direct
attempt therefore had its edit and write calls denied. After identifying the
error, the launcher was interrupted while the second attempt was in flight.

The [retained report](2026-11-08-staged-paired-v1-invalid.json) records one
failed direct attempt, one interrupted attempt with unknown outcome, and ten
unrun attempts. No failed or unfinished row is replaced. The first attempt
made five guarded local transport attempts, completed its model response in
52.923 seconds including subprocess setup and cleanup, and left the original
fixture unchanged. Its result is a harness failure, not an evaluation of the
model's ability to perform the direct task.

The frozen v1 harness is commit `a8681eba8854415a7b154ff067fb989b52b5d06f`;
the retained report identifies its plan, worker and runner hashes. A corrected
comparison must use a separately identified harness and a new output
directory. The primary actor case is now covered by an offline regression test.
