# Bounded repair paired experiment v1 — offline review checkpoint

This is a separate arithmetic comparison for issue #16, not canonical recovery-corpus qualification. No local endpoint, model, hosted provider, account, browser or server has been contacted while preparing this checkpoint. Root approval of this frozen harness and an explicit private admission file are required before live use. The admission template is deliberately unapproved and cannot run.

## Frozen comparison

Source: committed `929dfc00fe48fdd5140cd6f2332b7ff0ce115de8`, extracted from `git archive`; all 1,652 file hashes and exact internal documentation symlinks are in `source-manifest.json`. The earlier 0b89e59 prototype is retained separately and is not the live source. This experiment is not a full release qualification.

Three cases × two repeats × two arms = **12 attempts**, with direct/repair order for repeat 1 and repair/direct for repeat 2, within each case. No replacement attempts, fallback models, retries, automatic installs, downloads or resumed runs. A failure or unknown measurement stays in the denominator; unsafe cleanup or failed readiness leaves the remaining rows explicitly `NOT_RUN`.

- Addition/subtraction repair; immutable checks include positive and negative inputs.
- Pricing addition/multiplication repair; five immutable numeric checks include zero, negative and fractional values. This does **not** require the canonical corpus's failed then successful `python_exec`, which bounded repair intentionally disallows.
- Already-correct addition control; acceptance requires identical source bytes.

Within a pair, both arms get the same starting source, protected criteria, prompt, plan identity and settings. Both receive the same four concrete tools: read, write, edit, and verification of the one held plan. Only the arithmetic source can change; criteria stay byte-identical. Baseline runs `run_direct`; candidate runs `repair_direct` with two repairs and identical-failure limit 2. The candidate's initial successful check can legitimately use zero provider requests.

The final oracle independently parses the current source and evaluates a 24-point held-out numeric grid without executing generated Python. It also checks protected bytes and the unchanged control. The visible checker only executes one bounded pure arithmetic function after rejecting imports, calls, decorators, annotations, defaults, other statements and unbounded source. These are finite fixture criteria, not proof of general task correctness. Controller `scoped_pass` and model claims never replace the independent oracle. Ties establish no functional improvement; request/time differences are reported separately.

## Bounds and accounting

Each entire owned attempt has 300 seconds, including worker startup and setup, followed by at most 30 seconds of cleanup allowance. The supervisor permits 15 seconds of cooperative cancellation and then uses the reviewed pinned-process teardown. Cleanup-bound overrun or failure is explicitly unsuccessful. Workers and raw evidence are retained, never removed while owners may still act. Worker success plus nonzero exit is unsuccessful.

One shared runtime ledger covers all provider attempts, roles and inherited requests: 12 requests including retries/descendants, 10 tool rounds across repair attempts, zero SDK retries, zero delegation retry, 4,096 requested output tokens, 32,768 application context tokens, and 27,852 approximate serialized-input tokens. No delegation tool is exposed. Actual wire receipts retain configured provider, effective model, actor and task run ID. Missing final usage remains unknown; it is never replaced by zero. The transport's local-route billing assertion is separate from the ledger's unknown catalog pricing; hardware/electricity cost is not measured.

Raw requests/responses and events are capped at 2 MiB each; process logs at 2 MiB per stream; process samples at 8 MiB per attempt. Raw wire evidence contains only the synthetic task and isolated runtime, with a nonsecret local SDK placeholder; no user's provider credentials or home settings are inherited. The log is private. Stream/pull/SDK close and process ownership are joined before final receipts. Repeated SIGINT/SIGTERM during startup/cleanup retain the first control and wait for owned settlement.

The process sampler is used for identity/descendant ownership; its optional memory figures cover the **worker and observed descendants only**, not the borrowed server/model. Sampling can miss short-lived, unobserved reparented children. No cgroup, sandbox, total-memory, CPU-only, physical-cold, native responsiveness or hardware certification claim is made. Verifier/formatter argv are exact and bounded, generated code cannot start arbitrary subprocesses, and live worker socket audit permits only `127.0.0.1:8081`.

## Borrowed local server

The only live generation route is `POST http://127.0.0.1:8081/v1/chat/completions`, effective model `qwen38-27b-iq3s`. No alias, DNS, alternative port, proxy, redirect, automatic retry, server launch, model management or fallback is available. Port 8082 is never touched.

An explicit admission file binds the source manifest and Python harness hashes, expiry (at most two hours), current server PID/start ticks/argv digest, exact model path and file device/inode/size/mtime. The actual argv must name that file and model alias and must not request remote model resolution. This is an alias/process/file-stat binding, not a fresh GGUF cryptographic digest or proof of loaded tensors.

Before **every attempt**, bounded read-only `GET /health`, `/v1/models`, `/slots` require the one expected model and one idle slot. Unknown or busy state refuses, without waiting or modifying the daemon. At every model dispatch, process/listener/argv/model-file/admission identity is rechecked, including after connection setup immediately before HTTP/1.1 headers via the pinned `httpx 0.28.1 / httpcore 1.0.9` trace. `openai 2.21.0` is required. A test exercises the actual HTTP core trace with a synthetic network backend and proves zero HTTP bytes after connect-time revocation; it is not a real-server qualification.

This is a borrowed shared endpoint, not an exclusive reservation. Another caller can race the idle observation; remote cancellation/computation completion is not atomic with local cleanup. A later busy/readiness failure stops remaining work. Server template/tokenization and default reasoning behavior remain unchanged; the 27,852 estimator is approximate. No server or model profile is written, and cleanup never signals the borrowed server.

## Commands (no dependency installation)

Use the existing qualified Python 3.12 environment. Run from this directory:

```sh
export PYTHONPATH="$PWD/source/src:$PWD"
/tmp/henchman-v042-integrated-review/.venv/bin/python launch.py plan
/tmp/henchman-v042-integrated-review/.venv/bin/python -m unittest test_paired test_transport test_local_server test_launch test_worker -v
/tmp/henchman-v042-integrated-review/.venv/bin/python launch.py dry --output /tmp/henchman-paired-reviewed-dry-UNIQUE
/tmp/henchman-v042-integrated-review/.venv/bin/python launch.py admission-template
```

Only after root review and separate authorization: copy the template to an explicitly chosen private file, populate fresh read-only server identity/model-stat facts, set `approved: true`, set a short expiry, and `chmod 600` that file. The harness never grants this itself. Then the exact live command is:

```sh
/tmp/henchman-v042-integrated-review/.venv/bin/python launch.py live --admission /ABSOLUTE/PRIVATE/reviewed-admission.json --output /home/matthew/.cache/henchman-qualification/paired-929dfc0-UNIQUE
```

Output must be a new physical directory; overwriting/replacement cohorts are not supported. Each `attempt.json` is finalized after process settlement, `worker.json` records runtime/usage/oracle truth separately, and `receipt.json` retains all 12 rows plus six paired comparisons. The `dry` flag is present throughout, so scripted measurements cannot be mistaken for model measurements.
