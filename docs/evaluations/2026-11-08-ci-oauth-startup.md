# Windows OAuth startup test failure — 2026-11-08

The [Windows Python 3.14 installed-wheel job](https://github.com/mlg151/henchman-ai/actions/runs/42534244217/job/128895284167)
on `4bb932e` failed `test_full_login_claim_guard_rechecked_after_browser_ready[manager]`.
The test timed out after two seconds waiting for its synthetic launcher to be
created; the job otherwise reported 6,024 passed and 270 skipped. The captured
trace does not show whether TLS discovery or process startup was slow, or the
owned operation failed before launch, so the cause is unconfirmed.

That wait spans local TLS metadata discovery as well as subprocess creation.
The fixture now allows a bounded 40 seconds, watches the owned operation and
immediately surfaces any early exception or premature completion. It also
closes the controller and joins the operation if the wait fails. A local
control with a 2.1-second startup delay and an independent early-failure case
exercise the helper. The full synthetic OAuth flow also passed with a
2.1-second metadata response; this demonstrates one way the former wait could
expire, not the cause of the Windows failure. A 111-test related OAuth run
passed on Linux Python 3.11, and the final four affected cases passed on Linux
Python 3.11 and 3.12. The same four cases passed against an installed Linux
Python 3.12 development wheel using the wheel-smoke staging and origin check.
Production
OAuth deadlines and authorization guards are unchanged. Native CI must still
verify the revised test and can expose an underlying early failure.

The captured CI job log is retained in the local release-qualification cache
with SHA-256
`bef39c47cb5aba5c63292e380b4be568a1fb12f0edf2dd4162c47eaaf56601d1`.
