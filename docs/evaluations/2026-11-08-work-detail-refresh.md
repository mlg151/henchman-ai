# Work detail refresh — 2026-11-08

At `93133e3`, Textual work inspection refreshes the same task or agent while
its detail is open. A changed selection requires a fresh inspection; project,
session and owner checks remain in force. Returning to the list permits a
catalog refresh. Task details also identify the existing lack of interactive
terminal attachment.

The two new refresh regressions failed before the change. They exercise a real
background process producing output in two stages and refusal after a changed
selection. Both 80 × 24 and 120 × 40 refresh cases passed on Python 3.11 and
3.12. The broader Python 3.11 source run passed **90 work and interruption
tests**, and the Python 3.12 Textual work suite passed **30 tests** before the
additional size parameter was added. Ruff and mypy passed.

An offline wheel built from `93133e3` was installed into an isolated Python
3.12.13 environment; its module was imported from `site-packages`, and all
**91 work and interruption tests passed** with a separate home directory. The
wheel SHA-256 is
`364ffe0805899080b8f9fafe9010814dd32a4da77ac434bba5080be1bc75b3e6`;
the test log SHA-256 is
`a7ac0b36893b10bee8866489d674660f1a3d7a139f8e0a175bdf29f689166a40`.
The wheel is a 0.4.1 development artifact, not a native cross-platform or
v0.4.2 release qualification.

A later regression held the refresh read open while changing the selected item.
The read joined and its result was discarded; that case passed separately on
Python 3.11 and 3.12. It was added after the wheel run above.
