# Archived paired repair experiment v2

The [published result](../../docs/evaluations/2026-11-08-repair-paired-v2.md)
is direct 6/6 and bounded repair 6/6: six functional ties. This is separately
versioned fix validation, not general functional advantage, a speedup finding or
an isolated source ablation. The [v1 result](../../docs/evaluations/2026-11-08-repair-paired-v1.md)
remains direct 6/6 and repair 2/6, including its four failures.

This directory preserves 25 exact files named by `frozen-manifest.json`, plus the
original manifest itself and these reproduction notes. That includes all 13
Python files, the original README, plan, unapproved admission template, source
manifest, provenance, mutation inventory, harness patch, offline audit and three
offline logs. The manifest's remaining entry, `source.tar`, and the extracted
`source/` tree are deliberately not duplicated. The publication audit verified
that archive and all 1,690 source-file hashes and four internal symlink targets.
No Python caches, live private admission or raw experiment workspace is included.
The full live receipt and hash inventory of all 270 retained raw artifacts are in
the [JSON report](../../docs/evaluations/2026-11-08-repair-paired-v2.json).

`README.md` is the unchanged historical **pre-live** review checkpoint. Its
no-model-call statements and `frozen-manifest.json`'s `live_authorized: false`
describe that checkpoint; they do not deny the subsequent live cohort. Neither
these files nor the completed receipt authorizes another run. The historical
runtime environment and absolute paths in provenance are evidence, not portable
installation instructions.

For an intentional offline reproduction, copy this directory to a new private
experiment directory. Create `source/` there and extract `git archive
7141c1f342216b1a24defecb530931ca234f4c41` into it, preserving internal documentation
symlinks. The exact source archive SHA-256 is
`5cbe32c79f04a635b8b65e81c4ffb7f4c877124e6ab427ae1f46c79b89a25b31`.
`source-manifest.json` checks all source hashes, and the harness requires Henchman
imports from that tree. Use an existing environment matching `provenance.json`;
dependency installation and model downloads are outside this archive.

From that private copy, set `PYTHONDONTWRITEBYTECODE=1` and `PYTHONPATH` to its
absolute `source/src` and experiment paths. The historical README lists the
exact `launch.py plan`, five offline `unittest` modules, and `launch.py dry`
commands. They are separate from live execution. A dry run uses scripted
responses and cannot qualify model behavior; use a new output directory and
retain the complete fixed denominator, failures and unknown measurements.

Live use additionally requires fresh review and explicit authorization of the
exact local source/harness/server identities, followed by a new private admission
with a short expiry. The archived template is deliberately unapproved and empty;
the executed admission is excluded. The only permitted generation route is the
fixed local alias on port 8081. There is no server launch, model management,
proxy, redirect, fallback, hosted route or port 8082 access. Busy or changed
identity refuses. The borrowed endpoint is not exclusively reserved, and its
server/model/GPU memory is excluded from worker samples.

Both v2 arms use the same committed source. Initial fixtures, protected criteria,
user prompt, fixture plan identity and explicit settings match v1 byte-for-byte.
Full model messages do not: source 7141c1f includes the scoped tool-disclosure fix
and intervening delegation/prompt and other changes. The old `bounded-repair-paired-v1`
plan-ID namespace in `worker.py` is intentional fixture identity preservation,
not v1 execution authority. Never relabel changed source or model messages as an
unchanged experiment, and never replace the original negative v1 outcomes.
