# Paired repository-evidence experiment, v2 preparation

This separately versioned follow-up responds to the
[incomplete v1 run](../../docs/evaluations/2026-11-08-reuse-paired-v1.md); it
does not replace that result. Both arms still use the same three fixtures, two
repeats, tool catalog and independent bounded interpreter, differing only in
the supplied `combined` or `repository` search evidence. The v2 interpreter
supports an unshadowed empty `set()`. The tool guard allows bounded read-only
access to the fixture's generated verification status while continuing to deny
writes, links and oversized status files. Each attempt has a 450-second bound
and 30 seconds for cleanup, with no retries or replacement attempts. The fixed
request and tool-round limits remain 12 and 10 per attempt.
Acceptance requires completed execution, joined cleanup, no guard or audit
denials, an accepted current artifact, and fresh correlated verification after
cleanup. A denied tool call therefore makes the attempt unaccepted even if a
later artifact passes the narrow oracle; report those observations separately.

The [manifest](manifest.json) freezes the complete 21-script harness and source
commit. Reconstruct it by copying the unchanged v1 scripts first, then applying
these six v2 script files and the v1 source manifest. From the repository root,
with the project development environment installed:

```bash
experiment_dir="$(mktemp -d)"
project_python="$PWD/.venv/bin/python"
cp evals/repository_reuse_paired_v1/*.py \
  evals/repository_reuse_paired_v1/source-manifest.json "$experiment_dir/"
cp evals/repository_reuse_paired_v2/*.py "$experiment_dir/"
mkdir "$experiment_dir/source"
git archive d195ac18d3c2d586e30f29f218c7813e97c97269 | tar -x -C "$experiment_dir/source"
PYTHONPATH="$experiment_dir:$experiment_dir/source/src" \
  "$project_python" "$experiment_dir/launch.py" plan
```

As with v1, this is a constrained Linux profile and not a general-purpose
sandbox. A live run requires a freshly reviewed admission bound to the exact
local server, model file, source and harness; it never starts, changes or stops
that server and does not use hosted inference. Its finite oracle and any two
repeats cannot establish general reliability.

The offline synthetic preflight passed 49 focused checks on both Python 3.11
and 3.12, then all 12 scripted attempts. An independent audit checked six
paired inputs, joined worker identities and 790 raw files; its SHA-256 is in
the manifest. The 48 scripted requests did not use a model and show no quality
improvement. At preflight freeze no v2 live attempt had run.
