"""Fixed-denominator paired experiment. Default plan is completely offline."""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import signal
import sys
import threading
import time
from pathlib import Path
import contract as c
from memory_sampler import MemorySampler, signal_identity
from ownership import OwnedProcess
from transport import write_json


def harness_manifest():
    return {path.name: c.digest(path.read_bytes()) for path in sorted(c.HERE.glob("*.py"))}


def joined_thread(action, *, name):
    """Join startup/cleanup while deferring foreground SIGINT/SIGTERM.

    Signal handlers record the original control instead of raising in the
    narrow thread-registration window. Children inherit normal signal masks.
    The completion event, never Thread.join's interrupted flag, proves settlement.
    """
    values = {}
    controls = []
    settled = threading.Event()
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}

    def defer(signum, frame):
        old = previous[signum]
        if old is signal.SIG_IGN:
            return
        try:
            if callable(old):
                old(signum, frame)
            else:
                raise KeyboardInterrupt("paired signal " + str(signum))
        except BaseException as exc:
            controls.append(exc)

    def run():
        try:
            values["result"] = action()
        except BaseException as exc:
            values["error"] = exc
        finally:
            settled.set()

    for sig in previous:
        signal.signal(sig, defer)
    try:
        thread = threading.Thread(target=run, name=name, daemon=False)
        thread.start()
        while not settled.is_set():
            try:
                settled.wait(0.05)
            except (KeyboardInterrupt, SystemExit) as exc:
                controls.append(exc)
        while True:
            try:
                thread.join(0.05)
                if not thread.is_alive():
                    break
            except (KeyboardInterrupt, SystemExit) as exc:
                controls.append(exc)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if controls:
        values["control"] = controls[0]
    return values


def close_owned(owner, sampler=None):
    result = {"joined": True}

    def cleanup():
        if owner is not None:
            try:
                result["worker"] = owner.stop()
                result["joined"] = result["worker"].get(
                    "joined", not result["worker"].get("started")
                )
            except BaseException as exc:
                result.update(joined=False, error_type=type(exc).__name__)
        if sampler is not None:
            try:
                result["sampling"] = sampler.close()
            except BaseException as exc:
                result.update(joined=False, sampling_error_type=type(exc).__name__)

    joined = joined_thread(cleanup, name="paired-owned-cleanup")
    if joined.get("error") is not None:
        result.update(joined=False, error_type=type(joined["error"]).__name__)
    if joined.get("control") is not None:
        result["_primary_exception"] = joined["control"]
    return result


def run_one(
    root,
    row,
    *,
    dry,
    admission=None,
    command=None,
    attempt_seconds=c.ATTEMPT_SECONDS,
    cooperative_seconds=15,
):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    started = time.monotonic()
    result = {
        **row,
        "state": "setup_failed",
        "accepted": False,
        "cleanup": {"joined": False},
        "attempt_deadline_seconds": attempt_seconds,
        "cleanup_allowance_seconds": c.CLEANUP_SECONDS,
    }
    sampler = MemorySampler(
        output=root / "process-samples.jsonl", interval=0.1, byte_limit=8 * 1024 * 1024
    )
    owner = None
    primary = None
    timed_out = False
    timeout_at = None
    try:
        env = c.environment(root / "environment", Path(sys.executable))
        argv = command or [
            sys.executable,
            str(c.HERE / "worker.py"),
            "--output",
            str(root),
            "--case",
            row["fixture"],
            "--arm",
            row["arm"],
            "--repeat",
            str(row["repeat"]),
            *(["--dry"] if dry else ["--admission", str(admission)]),
        ]
        started_sampler = joined_thread(sampler.start, name="paired-sampler-start")
        if started_sampler.get("control") is not None:
            raise started_sampler["control"]
        if started_sampler.get("error") is not None:
            raise started_sampler["error"]
        owner = OwnedProcess(
            argv,
            cwd=c.HERE,
            env=env,
            artifacts=root / "process",
            sampler=sampler,
            role="attempt-worker",
        )
        started_owner = joined_thread(owner.start, name="paired-worker-start")
        if started_owner.get("control") is not None:
            raise started_owner["control"]
        if started_owner.get("error") is not None:
            raise started_owner["error"]
        result["worker_identity"] = owner.identity
        while owner.process.poll() is None:
            sampler.check()
            sampler.live("attempt-worker")
            if time.monotonic() - started >= attempt_seconds:
                timed_out = True
                timeout_at = time.monotonic()
                result["state"] = "timeout"
                signal_identity(owner.identity, signal.SIGTERM)
                grace = time.monotonic() + cooperative_seconds
                while owner.process.poll() is None and time.monotonic() < grace:
                    sampler.live("attempt-worker")
                    time.sleep(0.05)
                break
            time.sleep(0.05)
        if not timed_out:
            result["state"] = "worker_returned"
    except BaseException as exc:
        primary = exc
        result["error_type"] = type(exc).__name__
        result["state"] = (
            "interrupted" if isinstance(exc, (KeyboardInterrupt, SystemExit)) else "setup_failed"
        )
    finally:
        cleanup_started = time.monotonic()
        cleanup = close_owned(owner, sampler)
        cancel = cleanup.pop("_primary_exception", None)
        if cancel is not None and not isinstance(primary, (KeyboardInterrupt, SystemExit)):
            primary = cancel
            result["state"] = "interrupted"
        result["cleanup"] = cleanup
        result["process_sampling"] = cleanup.get("sampling")
        result["cleanup_seconds"] = time.monotonic() - (
            timeout_at if timeout_at is not None else cleanup_started
        )
        if result["cleanup_seconds"] > c.CLEANUP_SECONDS:
            result["cleanup"]["joined"] = False
            result["cleanup_bound_exceeded"] = True
        # Worker cannot mutate its result after the owner above is joined.
        path = root / "worker.json"
        if (
            cleanup["joined"]
            and path.is_file()
            and not path.is_symlink()
            and path.stat().st_size <= 4 * c.RAW_LIMIT
        ):
            try:
                worker = json.loads(path.read_bytes())
                result["worker"] = worker
                result["worker_sha256"] = c.digest(path.read_bytes())
                if result["state"] == "worker_returned":
                    result["state"] = worker["state"]
                if (
                    result["state"] == "finished"
                    and cleanup.get("worker", {}).get("returncode") != 0
                ):
                    result["state"] = "worker_exit_failed"
                result["accepted"] = (
                    result["state"] == "finished"
                    and worker["cleanup_joined"]
                    and worker["oracle"]["accepted"]
                    and worker.get("verification_current") is True
                    and not worker["denials"]
                )
            except (ValueError, KeyError, TypeError):
                result["state"] = "invalid_worker_receipt"
                result["accepted"] = False
        elif result["state"] == "worker_returned":
            result["state"] = "missing_worker_receipt"
        result["elapsed_including_setup_cleanup_seconds"] = time.monotonic() - started
        result["workspace_retained"] = True
        result["finalized_after_owned_cleanup"] = cleanup["joined"]
        write_json(root / "attempt.json", result)
    if primary is not None:
        raise primary
    return result


def execute(output, *, dry, admission=None):
    output = Path(output).absolute()
    if output.resolve() != output or not output.parent.is_dir():
        raise c.Denied("Physical existing output parent required")
    output.mkdir(mode=0o700, exist_ok=False)
    os.umask(0o077)
    receipt = {
        "version": c.VERSION,
        "dry": dry,
        "plan": c.plan(),
        "source": None,
        "memory_scope": "Worker and observed descendants only; borrowed model server excluded. No model memory/capacity claim.",
        "harness": harness_manifest(),
        "attempts": [
            {**row, "state": "NOT_RUN", "accepted": False} for row in c.plan()["attempts"]
        ],
        "qualification_pass": False,
        "finalized": False,
    }
    write_json(output / "plan.json", receipt)
    primary = None
    lease = None
    try:
        receipt["source"] = c.verify_source()
        if not dry:
            from local_server import Lease

            lease = Lease(admission)
        for index, row in enumerate(c.plan()["attempts"]):
            if lease:
                readiness = asyncio.run(lease.readiness())
                write_json(output / (row["attempt_id"] + "-readiness.json"), readiness)
            try:
                result = run_one(output / row["attempt_id"], row, dry=dry, admission=admission)
            except BaseException as exc:
                path = output / row["attempt_id"] / "attempt.json"
                receipt["attempts"][index] = (
                    json.loads(path.read_bytes())
                    if path.is_file()
                    else {
                        **row,
                        "state": "setup_failed",
                        "accepted": False,
                        "error_type": type(exc).__name__,
                    }
                )
                raise
            receipt["attempts"][index] = result
            if not result["cleanup"]["joined"]:
                raise c.Denied("Owned cleanup unavailable; remaining attempts not run")
    except BaseException as exc:
        primary = exc
        receipt["stop_error_type"] = type(exc).__name__
        if isinstance(exc, c.Denied):
            receipt["stop_reason"] = str(exc)
    finally:
        receipt["finalized"] = True
        receipt["qualification_pass"] = primary is None and all(
            row.get("accepted") for row in receipt["attempts"]
        )
        receipt["pairs"] = pair_summary(receipt["attempts"])
        receipt["summary"] = {
            "fixed_attempts": 12,
            "accepted": sum(row.get("accepted", False) for row in receipt["attempts"]),
            "not_run": sum(row["state"] == "NOT_RUN" for row in receipt["attempts"]),
            "meaning": "Harness/oracle outcomes only; dry runs do not measure model quality. Live pairs remain individually reported; ties are not improvement.",
        }
        write_json(output / "receipt.json", receipt)
    if isinstance(primary, (KeyboardInterrupt, SystemExit)):
        raise primary
    return receipt


def pair_summary(attempts):
    result = []
    for fixture in __import__("fixtures").CASES:
        for repeat in (1, 2):
            arms = {
                row["arm"]: row
                for row in attempts
                if row["fixture"] == fixture and row["repeat"] == repeat
            }
            values = {}
            for arm, row in arms.items():
                worker = row.get("worker", {})
                values[arm] = {
                    "state": row["state"],
                    "accepted": row["accepted"],
                    "artifact_oracle": worker.get("oracle"),
                    "requests": worker.get("transport_usage", {}).get("dispatched_requests"),
                    "usage_complete": worker.get("transport_usage", {}).get(
                        "all_dispatched_requests_have_complete_usage"
                    ),
                    "elapsed_including_setup_cleanup_seconds": row.get(
                        "elapsed_including_setup_cleanup_seconds"
                    ),
                }
            result.append(
                {
                    "fixture": fixture,
                    "repeat": repeat,
                    "arms": values,
                    "qualified_acceptance_delta": int(arms["repository"]["accepted"])
                    - int(arms["baseline"]["accepted"]),
                    "interpretation": "No functional improvement established when acceptance ties; request/time differences are separate observations.",
                }
            )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["plan", "dry", "live", "admission-template"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--admission", type=Path)
    args = parser.parse_args()
    if args.mode == "plan":
        print(json.dumps(c.plan(), indent=2))
        return 0
    if args.mode == "admission-template":
        print(
            json.dumps(
                {
                    "version": c.VERSION,
                    "approved": False,
                    "source_commit": c.COMMIT,
                    "source_manifest_sha256": c.digest(
                        (c.HERE / "source-manifest.json").read_bytes()
                    ),
                    "harness_sha256": c.digest(c.json_bytes(harness_manifest())),
                    "endpoint": c.ENDPOINT,
                    "model": c.MODEL,
                    "expires_unix": None,
                    "server": {"pid": None, "start_ticks": None, "cmdline_sha256": None},
                    "model_file": {
                        "path": None,
                        "device": None,
                        "inode": None,
                        "size": None,
                        "mtime_ns": None,
                    },
                },
                indent=2,
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required")
    if args.mode == "live" and args.admission is None:
        parser.error("live requires the explicit reviewed --admission file")

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("paired experiment interrupted")

    old = signal.signal(signal.SIGTERM, interrupted)
    try:
        result = execute(args.output, dry=args.mode == "dry", admission=args.admission)
    finally:
        signal.signal(signal.SIGTERM, old)
    print(json.dumps(result["summary"]))
    return 0 if result["qualification_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
