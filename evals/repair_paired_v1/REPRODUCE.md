# Archived paired repair experiment

The [published result](../../docs/evaluations/2026-11-08-repair-paired-v1.md)
is negative: direct 6/6, bounded repair 2/6. This directory preserves the exact
18 files in `frozen-manifest.json`. `README.md` describes their historical
pre-live review checkpoint; its no-model-call statement applies to that checkpoint,
not the subsequent live cohort. The manifest is historical evidence, not fresh
run authorization.

The required `source/` tree is not duplicated. For an intentional offline
reproduction, copy this directory to a new private experiment directory, create
`source/` there, and extract the output of `git archive
929dfc00fe48fdd5140cd6f2332b7ff0ce115de8` into it. Preserve internal documentation
symlinks. `source-manifest.json` checks all 1,652 source files and requires imported
Henchman code to come from that tree. Use an existing Python environment matching
`provenance.json`; dependency/model installation is outside this archive.

From the copy, set `PYTHONPATH` to its absolute `source/src` and experiment paths.
`launch.py plan` and the five `unittest` modules listed in the historical README
perform no model calls. `launch.py dry --output <new-directory>` uses synthetic
responses and cannot qualify live behavior. Output directories must be new;
retain failures and fixed denominators.

Live use additionally needs fresh review of the exact server/source/harness
identities and a private admission file. The archived template is unapproved and
unpopulated; the executed admission is not published. The historical route allows
only the fixed local alias on port 8081, with no server launch, management,
fallback, hosted route or port 8082 access. Expired, busy or changed identity
refuses. Never relabel a changed source, prompt, tool surface or harness as the
original cohort. See the historical README for full bounds and shared-server limits.
