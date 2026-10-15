# File-edit recovery checkpoint — 2026-10-14

The active coding-agent goal made concrete progress through tool contract fixes,
offline regressions, installed-package verification and retained live failures.
The overall goal remains active. No commit, push or publication was performed.

## Changes

- `edit_file` rejects partial line ranges even when `old_str` is provided; the
  old implementation silently ignored a lone bound and could write the file.
- Tool/property descriptions explain mutually exclusive modes, full inclusive
  range replacement, current coordinates and unique surrounding context.
  Multiple-match errors give fresh-read/context retry guidance and do not write.
- `read_file(line_numbers=true)` exposes absolute 1-based line prefixes. Plain
  output remains the default. Prefixes count toward the existing character limit;
  the truncation notice is additional. This is not a total input-memory bound.
- Review found a coordinate mismatch: `splitlines` treated form feeds, vertical
  tabs and Unicode separators as boundaries unlike normal file iteration.
  Line edits now use `StringIO(...).readlines()` after `atomic_read` normalizes
  CR/CRLF, matching numbered reads. All five separator regressions first failed.
- Docs, changelog and roadmap updated. Installed-wheel staging includes the
  existing file-tool suite plus new numbered-read and edit-recovery tests.
- The newly staged existing traversal test assumed `/etc/passwd` existed at a
  specific relative depth. It now uses an existing isolated temporary fixture
  and asserts that rejection preserves its contents.

No syntax guard, new rename mode, schema `oneOf`, or relaxed evaluation criteria
was introduced. Existing unique-string replacement and EOF clamping remain.

## Verification

- Numbered-read initial red: 4 failed / 1 passed (`numbered-read-red.log`).
- Edit-recovery initial red: worker observed 6 failed / 2 passed.
- Coordinate mismatch red: 5 failed / 5 passed
  (`numbered-read-coordinate-red.log`).
- Final source selection: **98 passed**, 12.56 seconds
  (`edit-recovery-source-final.log`): existing/new file tools, edit eval contracts
  and five-adapter coding-loop tests.
- Final fresh installed wheel: **527 passed**, 44.71 seconds, Linux / Python3.12
  (`edit-recovery-wheel-linux-final.log`). Rebuilt and force-reinstalled after the
  coordinate fix. Initial wheel run had 521 passes / one host-layout test failure,
  retained in `edit-recovery-wheel-linux.log`.
- Ruff clean across six touched Python files; mypy clean across the two production
  modules and two new test modules. Scoped diff checks clean.
- Independent reviewer reproduced the coordinate bug, then verified its fix and
  all 18 new tests. No full-suite or native Windows/macOS verification claim.

## Live evidence and next gap

Reused the pinned Qwen3-4B-Instruct-2507 Q8_0 / llama.cpp b11617 Vulkan profile
from the preceding checkpoint. No downloads, provider fallback or budget changes.
Same 10-round/60-second scenario limits, 6144 input / 1024 output tokens and seed42.
The host remains a 60GiB RAM / RTX3090 24GiB system, not the 16GB target laptop.

Report: `local-model-16gb-probe/qwen3-4b-edit-recovery-vulkan.json`, with matching
probe/server logs. This run preceded the separator-only coordinate fix and final
test-fixture repair. These scenarios contain ordinary newlines.

- Class extension passed (3.12s).
- Counter refactor passed (4.90s).
- Scoped rename failed independent parsing (2.15s): the model read plain text,
  guessed ranges 4–7, 12–15 and 20–23, and produced invalid indentation. Runtime
  reported success, demonstrating why independent correctness checks remain needed.
- Multi-file edit failed independent Python verification (7.18s): after a missing
  target error, the model requested numbered output but replaced lines4–6 with a
  whole class and later lines5–6 with a whole application, creating invalid code.
  Better coordinates and guidance alone did not enforce correct replacement scope.

Result: **2/4**, versus 3/4 in the preceding single run. This is no demonstrated
model-quality improvement, controlled benchmark, cross-provider result or local
default qualification. Do not hide these failures or weaken the independent
oracles. Future work should address actual verification/recovery behavior rather
than assuming successful edits establish correctness. A semantic edit guard would
be a separate policy decision, with intermediate-edit and Python-version concerns.

Owned server PID2771762 exited0 and was confirmed absent. Existing unrelated
Ollama service was left alone. No owned model server remains running.
