# Paired repository-evidence experiment

This is a constrained experiment for comparing supplied `combined` and
`repository` search results on three small helper-reuse fixtures, with two
repeats per arm. The independent oracle uses bounded AST interpretation and
harness-defined helper behavior; it does not execute candidate code, prove
general correctness, or measure the canonical recovery corpus. A tie does not
establish improvement. Search results are untrusted data.
Acceptance requires completed execution, joined cleanup, no guard or audit
denials, an accepted current artifact, and fresh correlated verification after
cleanup. A denied tool call makes the attempt unaccepted even if a later
artifact passes the narrow oracle.

The scripts and manifest freeze source commit
`d195ac18d3c2d586e30f29f218c7813e97c97269`. They are an experimental Linux
profile, not a general-purpose sandbox. Their path guards, process checks and
network restrictions apply only to the explicitly constructed fixture and
reviewed local server. Never point the worker at a valuable project. The live
profile requires the exact loopback endpoint and model in `contract.py`, a
fresh private admission bound to the server process, model file, source and
harness, and an idle server. It does not start, reconfigure or stop the server,
use hosted inference, or retry failed attempts.

The offline preflight uses scripted responses and exercises integration without
calling a model; its outcomes are not model-quality evidence. For a fresh
private working copy, from the repository root with the development environment
already installed:

```bash
experiment_dir="$(mktemp -d)"
project_python="$PWD/.venv/bin/python"
cp evals/repository_reuse_paired_v1/*.py \
  evals/repository_reuse_paired_v1/source-manifest.json "$experiment_dir/"
mkdir "$experiment_dir/source"
git archive d195ac18d3c2d586e30f29f218c7813e97c97269 | tar -x -C "$experiment_dir/source"
PYTHONPATH="$experiment_dir:$experiment_dir/source/src" \
  "$project_python" "$experiment_dir/launch.py" plan
```

Use the project's development Python with `PYTHONPATH` set to the experiment
directory and its `source/src` directory. `launch.py plan` only prints the
contract. `launch.py dry --output <new-absolute-path>` runs the synthetic
preflight and creates retained fixture workspaces under that new path. The
output parent must already exist and be a physical directory. The focused
`test_*.py` modules cover guards, cleanup, transport faults, oracle behavior
and preparation; they also require Git and the development dependencies. The
live HTTP guard additionally pins the tested HTTPX/httpcore versions. Review
the fixed limits, receipts and limitations before interpreting any live run.
