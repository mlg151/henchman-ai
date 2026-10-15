# Platform portability checkpoint

## Subsequent unrestricted verification

The environment was changed to unrestricted after the original checkpoint below.
Root reran tests/e2e/test_coding_loop.py: all 12 cases passed in 10.12s on Linux
Python 3.14.4 (ten real-tool workflows plus two malformed-call guards).

A fresh Python 3.12.7 environment installed the built wheel and dependencies, then
ran tests/testing/installed_wheel_smoke.py. First runs exposed stale timestamp
bytecode in the instantaneous same-size +/- fixture edit: the source was correct,
but a second Python process executed cached subtraction. A deterministic two-run
probe reproduced this with bytecode enabled and avoided it with writes disabled.
The fixture now sets PYTHONDONTWRITEBYTECODE for its child processes.

Final installed-artifact smoke after the input-tool repair and wheel
rebuild/reinstall: 82 passed in 24.71s, with installed import origin
verified outside checkout, both CLI aliases tested, and local RAG storage verified.
Log: .agent_tasks/portable-wheel-linux-final.log. Native Windows/macOS still need
real runs; provider responses are scripted. No project push/commit performed.

## Original bounded-sandbox checkpoint (historical)

The prior coding-loop turn made verified progress. This turn fixes concrete native
platform defects and prepares installed-artifact CI; it does not certify all OSes.

## Implemented and verified

- Shell imports Unix terminal modules lazily, routes Windows through its native
  shell without Unix sudo rewriting, and consults procfs only on Linux with procfs
  available. Process names containing spaces/parentheses parse correctly.
- RAG uses lazy native POSIX/Windows interprocess locks; Windows locks/unlocks the
  same byte at offset zero, and acquiring a lock no longer truncates its file.
- Install detection recognizes Windows uv/pipx separators/case while retaining
  original executable argv and manual fallback for ambiguous/unknown installs.
- PythonExec supplies a child-only UTF-8 output encoding. A real subprocess test
  verifies Unicode stdout/stderr under inherited cp1252, workspace paths with
  spaces, preservation of other environment variables, and unchanged parent env.
- Independent Python 3.12 CI matrix for Ubuntu/macOS/Windows builds and installs a
  wheel, stages tests outside checkout, verifies installed import origin in pytest,
  checks both CLI aliases, native RAG operations/locking, Python execution, shell
  portability, and all five-provider read/edit/test/recover cases. Default/inherited
  encoding is preserved. No source-prepending repository conftest is copied.

Final combined local gate: **158 passed, 10 deselected**, 15.95s on Linux/Python
3.14.4. Scope: shell portability/execution/PTY helpers, PythonExec, RAG locks,
system-info/upgrade/doctor, installed-wheel staging helpers, malformed OpenRouter
calls. One third-party Chroma deprecation warning. The ten real coding-loop tests
remain explicitly unverified due the previously reproduced AnyIO thread stall.

Ruff clean for four production modules and seven relevant tests/helpers; mypy clean
for production modules plus installed-wheel helper. Scoped diff check clean.
`uv build --no-build-isolation --out-dir .agent_tasks/portability-dist` successfully
built the source distribution and wheel. Building is not installed-runtime proof.
Bounded specialist review found no new actionable defects in this slice.

## Limits and next work

- Hosted native OS jobs have not run. No push, publication, fresh installation,
  live inference, benchmark, or native Windows/macOS execution claimed.
- Known next reliability gaps from the audit: several Python-driven test/lint/pip
  subprocesses still inherit legacy encoding despite UTF-8 decoding. PythonExec
  termination can wait indefinitely if SIGTERM is ignored; formatter/linter/pip
  timeout cleanup needs verification. Shell descendant cleanup also needs a focused
  lifecycle audit. These were outside this bounded portability change.
- Preserve the large preexisting dirty tree. No commits/staging/reset occurred.

The user expanded the goal during this turn: focus on Python developers, great
organized pythonic code, DevOps, smell-free code, checking for existing functionality
before adding it, and leading a whole development team. These are additional real
requirements, not satisfied by the portability checks. Next discovery covers
existing registered Python analysis/reuse tools, verification/DevOps, and actual
team orchestration. Keep the full updated goal active.
