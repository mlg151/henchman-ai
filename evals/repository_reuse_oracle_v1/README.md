# Repository reuse oracle prototype

This offline prototype checks three small fixture tasks using a bounded AST
interpreter and harness-defined helper behavior. It never executes candidate or
helper source. A separate call-recorder probe rejects copied helper logic, and
protected file bytes must match the fixture. Supported Python constructs and
input-preservation limits are deliberately narrow; unsupported code is an
unverified failure, not proof that the code is incorrect.
The standalone `checker.py` reports that oracle's structured result and exit
status for one fixture in the current directory; it is not yet bound to a runtime
verification tool.

This is only an oracle for preparing a future supplied-evidence comparison. It is
not the full experiment: retrieval preparation, a supervised worker, live paired
attempts and their evidence are still missing. The stub, checker, fixture
examples, and helper simulators may share mistakes; the finite examples do not
prove general correctness. No model calls are made by these tests.

Run from the repository root with:

```bash
python -I -B -m unittest discover -s evals/repository_reuse_oracle_v1 -p 'test_*.py' -v
```
