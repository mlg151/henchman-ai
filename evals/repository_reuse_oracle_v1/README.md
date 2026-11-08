# Repository reuse oracle prototype

This offline prototype checks three small fixture tasks using a bounded AST
interpreter and harness-defined helper behavior. It never executes candidate or
helper source. A separate call-recorder probe rejects copied helper logic, and
protected file bytes must match the fixture. Supported Python constructs and
input-preservation limits are deliberately narrow; unsupported code is an
unverified failure, not proof that the code is incorrect.
The prototype supports an unshadowed zero-argument `set()` and bounded
`set.add`; calls with arguments and locally shadowed `set` are unsupported.
The separately frozen paired experiment retains its original interpreter.
The standalone `checker.py` reports that oracle's structured result and exit
status for one fixture in the current directory; it is not yet bound to a runtime
verification tool.

This is only an oracle prototype, not the full experiment. The separate
[paired harness](../repository_reuse_paired_v1/README.md) and its recorded
incomplete live run use the earlier frozen interpreter. The stub, checker, fixture
examples, and helper simulators may share mistakes; the finite examples do not
prove general correctness. No model calls are made by these tests.

Run from the repository root with:

```bash
python -I -B -m unittest discover -s evals/repository_reuse_oracle_v1 -p 'test_*.py' -v
```
