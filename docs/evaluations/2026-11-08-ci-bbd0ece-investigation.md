# CI task cleanup investigation — 2026-11-08

The [CI run for `bbd0ece`](https://github.com/mlg151/henchman-ai/actions/runs/42500572450)
reported failures in the macOS 3.12 and 3.14 installed-wheel jobs, and the
aggregate gate failed. The other 17 jobs passed, including every Windows and
Linux wheel job. The Python 3.12 source/coverage job passed 12,665 tests with
91 skipped and 91.26% coverage. Native verification of the subsequent fix is
separate evidence.

The macOS 3.12 job had **6,117 passed, 83 skipped, and one failure**. In
`test_capture_short_writes_and_cleanup_faults_settle_owned_process[zero_write]`,
the observed task status was `outcome_unknown`, the direct child return code was
zero, and metadata reported `Task cleanup failed: [Errno 1] Operation not
permitted` while output capture independently reported a zero-progress write.
The macOS 3.14 job had the same passed/skipped/failure totals; its test cleanup
then called `stop_task` on the no-longer-owned unknown record, masking the prior
assertion with `TaskOwnershipError`. Neither log identifies the particular
process-group signal that returned the permission error.

The macOS logs are retained locally under
`~/.cache/henchman-release-qualification/ci-bbd0ece-42500572450/`. Their
SHA-256 hashes are `5199046ead6ebf5d1c0a8a95b97109f343925f3d91923a1e49b18047ef809239`
for 3.12 and `de740ff1ecdad5273f8454e292443390065b729f5d790dc2fe94737840299af6`
for 3.14. The jobs remain available in the linked CI run.
The Python 3.12 source log SHA-256 is
`f99bed568498e86268e0e71ea3ae5ec7e238a7cbd9a58ba7d2f8c1b1e4d8bf02`.

One plausible race is Darwin returning a process-group permission error while
the exited child is awaiting reaping; the logs alone do not establish that as
the cause. The subsequent implementation waits a bounded time for the owned
child, then rechecks the group; a still-live child or persistent permission
error remains a cleanup failure. It also labels a denied final group SIGKILL so
a future failure identifies that phase. The fault test no longer masks an
unknown outcome by stopping a task whose handle has already been retired.

The new deterministic tests cover a vanished group, a still-signalable group,
persistent denial, a child that remains live, final SIGKILL denial, and a real
child with a simulated capture failure and first-signal denial. Before the fix,
three of the first four simulated cases failed. Python 3.11 focused source tests
passed 124 tests after the final-signal diagnostic; Python 3.12 source tests
passed 72. A clean wheel built from `7363e61a39246d367b229465672d5151fb33f991`
and installed in an isolated Python 3.12.13 environment passed **124 focused
tests**. Its wheel SHA-256 is
`6944de9a1e66f003e1858bafd2e944b753db7b54b6f82b07f71f10c81ee968d8`,
and the local test log SHA-256 is
`d1fb7b33228c8880aa5f5485da092cca701625b9bd23c1f200be5d9e044fe08e`.
This was a development wheel reporting 0.4.1, not a v0.4.2 release artifact.

The [Apple XNU source](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sig.c)
and [killpg manual](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/killpg.2.html)
are useful context; neither substitutes for a fresh native run of the fix.

## Native follow-up

The installed-wheel jobs in the [subsequent CI run on `4ba6f71`](https://github.com/mlg151/henchman-ai/actions/runs/42504651298)
passed on all four macOS Python versions. Each previously failing macOS 3.12 and
3.14 job reported **6,124 passed, 83 skipped**. The retained 3.12 and 3.14 job
log SHA-256 values are
`51fd09f5827475ded8c1d1319dd4a9eb257600c3656ef0c971bd688637f15d3d` and
`e6c481a86f08cfd0a3fa492855ee2365e97e7778e7f343cc67b41ccabc2781a1`.
The jobs include the deterministic simulated race; they do not establish that
the original intermittent kernel condition occurred again. The remainder of
the run was still in progress when this follow-up was recorded.
