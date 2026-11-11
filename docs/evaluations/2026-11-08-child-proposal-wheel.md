# Child proposal publication: clean-wheel check — 2026-11-08

An isolated Linux Python 3.12.13 run of the wheel built from clean commit
`8730634bb8ced74eb3c8ee6feefb25e056607b0f` passed **29 focused tests**:
the private proposal suite and checkpoint-verification suite. The staged test
environment checked the installed package origin and blocked network access.
An independent byte comparison matched all 455 installed package files to the
wheel. The checkout was clean; the user's uncommitted workspace changes were
not part of the artifact.

The tests cover staged edit/create/delete, current-file conflicts, concurrent
checkpoint publication, retained originals, eight process-exit points,
credential rotation and verification invalidation. The second run retained
its log under `proposal-wheel-8730634/pytest.log` in the release-qualification
cache. Its SHA-256 is
`dacf92444e4406b7d0412ce63de3aa1a61c28ed5cce8852e4440e63a1ee0f494`.

The local wheel SHA-256 is
`84ec75c6b213df349ed36a80c565e09abb9c1d396d792033635ea92691002aae`;
the source archive SHA-256 is
`f10e6661860fe84a53de865a8914843d49c8d5d4815a6333fabeb3adeeafd670`.
Both identify this development build, whose package version remains `0.4.1`.
They are not final release artifacts.

This validates the internal publication service on Linux only. The service is
not yet wired to delegated tool execution, child-worker ownership or parent
approval. Native Windows tests were added to the installed-wheel matrix but
have not yet run, and matched live-agent effectiveness remains open. No
filesystem sandbox or completed issue #29 is claimed.
