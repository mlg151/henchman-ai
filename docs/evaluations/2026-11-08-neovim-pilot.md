# Installed Neovim pilot checkpoint — 2026-11-08

The opt-in pilot passed its scoped installed-package fixture on **Linux,
Python 3.12.13 and Neovim 0.12.6**. A fresh environment installed the development
`0.4.1` wheel with SHA-256
`f78d0aa8b4ef08a74207cc4c304f96e1f43e08c4e4e01f2147a0b48320ddda7b`.
This qualifies the recorded integration fixture, not the final v0.4.2 artifact
or model quality. The [receipt](2026-11-08-neovim-pilot.json) retains source,
artifact and log identities. See the [pilot guide](../neovim.md) for use and limits.

The author and independent reviewer each ran the same 132 permanent tests from
the installed wheel, outside the checkout. Both passed; the independent run
finished in 63.16 seconds. These include 56 actual Neovim subprocess cases,
36 selected-file guard cases, 36 stdio cases and four export cases. They are
132 distinct tests, not 264 distinct observations. The reviewer additionally
passed 13 malformed-frame/lifecycle probes and 35 strict-JSON differential probes.

The real editor launches the installed Henchman runtime and talks to an owned
loopback HTTP/SSE fixture with scripted responses. The successful path reads a
calculator, edits addition, runs its test and opens a run-correlated recorded
diff. An independent pytest invocation passes afterward. The denial path keeps
the bad source unchanged and retains the failing test outcome. Cancellation
joins the real runtime and leaves files unchanged. No live model or hosted
provider was used.

The fixture preserves unrelated dirty disk content, an unsaved editor draft and
the exact Git index bytes. Selected dirty buffers are refused. Buffer changes,
late callbacks, malformed JSON/correlation, EOF and owned process exit are
covered separately. A completion marker prevents a premature zero editor exit
from passing an unfinished Lua test. Regressions were demonstrated before the
strict decoding and correlation repairs; accepted terminal results still state
`task_verified: false`.

Reproduce the permanent cohort with the exact supported editor available:

```bash
HENCHMAN_TEST_NVIM=/absolute/path/to/nvim python -m pytest --no-cov \
  tests/integrations/test_neovim_pilot.py \
  tests/integrations/test_neovim_scope.py \
  tests/integrations/test_blueprints.py tests/cli/test_headless_stdio.py
```

Use an isolated wheel environment and staged test files, and verify package
origin as in the [release process](../../CONTRIBUTING.md#-release-process).
A missing or different editor produces skips and does not qualify the pilot.
Other editor versions, Windows/macOS, native assistive technology, human
usability and live coding performance remain unqualified. The independent
additional probes and raw logs were retained locally; the permanent regression
cases and hash receipt are committed.
