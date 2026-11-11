# Selected-file check inspection — 2026-11-08

The checkpoint review change at `f96c374` identifies exact declared-input
matches for a selected file and places those plans first. It retains other plans,
reports unavailable input specifications explicitly, and labels each displayed
status as belonging to the whole plan. Neither a match nor a nonmatch establishes
complete coverage; no checks are executed and no plan records are rewritten.

The new rendered regressions initially failed at 80 × 24 and 120 × 40 before
the change. The Python 3.11 checkpoint suite then passed 49 tests, and the three
selected-file cases, including a credential-redacted plan, passed separately.
Python 3.12 passed all 50 source tests. Ruff and mypy passed for the touched
production module and tests.

A clean wheel built offline from `f96c374` was installed into an isolated Python
3.12.13 environment. The imported module came from that environment's
`site-packages`; all **50 checkpoint tests passed** with a separate home
directory. The wheel SHA-256 is
`aea43ddf32a593c893a8ccf6187aa0f0bd88a40887e885769e40ed862fac398a`;
the test log SHA-256 is
`7ac161eeed88b71972edf66aeb7d2b58ff065a716c83e61594bf13fd0bfbf8ce`.
This development wheel reports 0.4.1. It is neither a native macOS/Windows
result nor a final release artifact. Physical-terminal and accessibility
qualification remain open.

The follow-up at `6339138` adds current status for individual checks that
declare the selected file. A passing selected-file check remains distinct from
an unrelated failing check in the same plan; stale or insufficiently declared
inputs do not become current passes. The full checkpoint suite passed **52
tests** each on Python 3.11 and 3.12, and Ruff/mypy passed. A clean wheel from
that commit, imported from its isolated Python 3.12.13 `site-packages`, also
passed all **52 tests**. Its wheel SHA-256 is
`c2f9bba29641f2eec7c1ff6ed6547859b64c0e1f470f3e7383f6d32f68a2d831`;
its log SHA-256 is
`2767d5a8651e6dc966c744b2d66168afc50bcc6324f476147aa25cbaf84a96e6`.
