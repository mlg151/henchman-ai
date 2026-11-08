# Local direct versus staged comparison

This frozen comparison plans three separate toy fixtures, two repeats and two
arms: twelve attempts total. The direct arm is confined to the fixture and
cannot delegate; the staged arm is confined to the same fixture and requires
the dynamic staged route. Both use the same installed development wheel, local
model, request limit and serialized test transport. Arm order alternates across
repeats. The fixture task is identical across arms; the route instructions
necessarily differ, so this is a workflow comparison rather than a pure code
ablation.

Each attempt runs in a separate process and a new private workspace with an
empty home and no inherited API credentials or proxies. The transport admits
only the fixed localhost endpoint and model, checks an idle slot and never
selects a hosted fallback. The local server is shared and is not exclusively
reserved; the reported model alias does not prove the loaded weight identity.
The worker has twelve requests and 240 seconds; the launcher allows
30 seconds more for cleanup. Output is recorded after each attempt, including
failures and unrun rows. No generated Python is executed: the parent compares
current file bytes to a deliberately narrow expected AST and checks observed
tool outcomes. Equivalent alternative implementations can be rejected.

Timing includes subprocess startup, review and cleanup. Linux worker peak RSS
excludes formatter subprocesses, the model server and GPU. Request counts are
recorded; complete token usage, hardware cost and electricity are not. These
limits prevent this comparison from establishing whole-application memory,
production provider scheduling or performance on a 16 GB laptop.

`plan` makes no model requests:

```bash
python evals/staged_delegation_paired/runner.py plan
```

`live` makes local model requests and requires the exact frozen wheel plus a
new absolute output directory whose parent already exists:

```bash
python evals/staged_delegation_paired/runner.py live \
  --wheel /absolute/path/to/the/frozen.whl \
  --output /absolute/path/to/a/new/result-directory
```

The launcher verifies the plan hash, wheel hash and installed package bytes
before each attempt. The fixed route, fixture list, arm order and limits are in
[plan.json](plan.json); local guard and oracle checks are in
[`test_staged_delegation_paired.py`](../../tests/testing/test_staged_delegation_paired.py).
