"""Reproduce the exact retained v2 live-run audit; never execute candidate code."""

import hashlib
import json
import os
import sys
from contextlib import suppress
from pathlib import Path

if not __debug__:
    raise SystemExit("Run the audit without Python optimization")
if len(sys.argv) != 3:
    raise SystemExit(
        "Usage: audit_repository_reuse_v2.py <qualification-directory> <new-output-json>"
    )
base = Path(sys.argv[1]).resolve(strict=True)
harness = base / "retrieval-paired-v2-d195-preparation"
out = base / "retrieval-paired-v2-d195-live"
path = Path(sys.argv[2]).absolute()
if (
    path.resolve() != path
    or not path.parent.is_dir()
    or path.is_relative_to(out)
    or path.is_relative_to(harness)
):
    raise SystemExit("Output must be a new physical path outside the retained inputs")
sys.path.insert(0, str(harness))
sys.path.insert(1, str(harness / "source/src"))
import contract as c  # noqa: E402
import fixtures  # noqa: E402
from launch import harness_manifest  # noqa: E402


def sha(value):
    return hashlib.sha256(value).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


pre = read(harness / "preflight-manifest.json")
assert (
    sha((harness / "preflight-manifest.json").read_bytes())
    == "ebf4b21d4d179334b12315f9823d883b506f5c4f2fc5fdd5be437a89ea884b13"
)
assert (
    harness_manifest() == pre["python_files"]
    and c.verify_source()["manifest_sha256"] == pre["source_manifest_sha256"]
)
source = read(harness / "source-manifest.json")
actual = {
    str(p.relative_to(harness / "source"))
    for p in (harness / "source").rglob("*")
    if p.is_file() or p.is_symlink()
}
assert actual == set(source["files"])
for name, expected in source["files"].items():
    p = harness / "source" / name
    assert sha(p.read_bytes()) == expected
    if name in source["symlinks"]:
        assert p.is_symlink() and os.readlink(p) == source["symlinks"][name]
r = read(out / "receipt.json")
assert r["finalized"] and not r["dry"] and len(r["attempts"]) == 12
assert [a["attempt_id"] for a in r["attempts"]] == [a["attempt_id"] for a in c.plan()["attempts"]]
assert (
    not r["qualification_pass"] and r["summary"]["accepted"] == 8 and r["summary"]["not_run"] == 0
)
attempts = []
for a in r["attempts"]:
    p = out / a["attempt_id"]
    w = read(p / "worker.json")
    events = read(p / "events.json")
    assert a["cleanup"]["joined"] and a["finalized_after_owned_cleanup"] and w == a["worker"]
    assert sha((p / "worker.json").read_bytes()) == a["worker_sha256"] and w["cleanup_joined"]
    identity = a["worker_identity"]
    proc = Path("/proc") / str(identity["pid"]) / "stat"
    if proc.exists():
        stat = proc.read_text()
        assert int(stat[stat.rfind(")") + 2 :].split()[19]) != identity["start_ticks"]
    oracle = fixtures.oracle(p / "workspace", a["fixture"])
    assert oracle["accepted"] == w["oracle"]["accepted"] and oracle.get("source_sha256") == w[
        "oracle"
    ].get("source_sha256")
    ready = read(out / (a["attempt_id"] + "-readiness.json"))
    assert (
        ready["/health"] == {"status": "ok"}
        and len(ready["/slots"]) == 1
        and ready["/slots"][0]["is_processing"] is False
    )
    assert len(ready["/v1/models"]["data"]) == 1 and ready["/v1/models"]["data"][0]["id"] == c.MODEL
    retrieval = read(p / "retrieval.json")
    assert retrieval["status"] == "complete" and retrieval["arguments"]["strategy"] == (
        "combined" if a["arm"] == "baseline" else "repository"
    )
    assert sha(retrieval["content"].encode()) == retrieval["content_sha256"]
    u = w["transport_usage"]
    requests = sorted((p / "wire").glob("request-*.json"))
    assert len(requests) == u["dispatched_requests"] == len(w["requests"])
    for request in requests:
        assert read(request)["model"] == c.MODEL
    if w.get("verification_current"):
        final = w["verification_final"]
        status = final["status"]
        assert final["current"] and status["current_checks_passed"]
        run_id = status["run_id"]
        plan_id = status["plan_id"]
        ids = {
            e["data"]["id"]
            for e in events
            if e.get("type") == "tool_call_request"
            and e["data"].get("name") == "verify_plan_execution"
            and e["data"].get("arguments") == {"action": "verify", "plan_id": plan_id}
        }
        matched = []
        for e in events:
            d = e.get("data", {})
            if (
                e.get("type") == "tool_call_result"
                and d.get("tool_call_id") in ids
                and d.get("success")
            ):
                with suppress(KeyError, TypeError, ValueError):
                    matched.append(json.loads(d["result"]).get("run_id"))
        assert run_id in matched
    computed = (
        a["state"] == "finished"
        and a["cleanup"]["joined"]
        and w["cleanup_joined"]
        and oracle["accepted"]
        and w.get("verification_current") is True
        and not w["denials"]
        and a["cleanup"]["worker"]["returncode"] == 0
    )
    assert a["accepted"] == computed
    attempts.append(
        {
            "attempt": a["attempt_id"],
            "state": a["state"],
            "accepted": a["accepted"],
            "oracle_accepted": oracle["accepted"],
            "verification_current_after_cleanup": bool(w.get("verification_current")),
            "denials": w["denials"],
            "tool_failures": w.get("tool_failures", []),
            "requests": u["dispatched_requests"],
            "usage_complete_requests": u["usage_complete_requests"],
            "known_prompt_tokens": u["known_prompt_tokens"],
            "known_completion_tokens": u["known_completion_tokens"],
            "elapsed_seconds": a["elapsed_including_setup_cleanup_seconds"],
            "worker_identity_absent": True,
        }
    )
pairs = []
for case in fixtures.CASES:
    for repeat in (1, 2):
        baseline = out / f"{case}-{repeat}-baseline"
        rr = out / f"{case}-{repeat}-repository"
        li, ri = read(baseline / "input.json"), read(rr / "input.json")
        lw, rw = read(baseline / "worker.json"), read(rr / "worker.json")
        lr, rt = read(baseline / "retrieval.json"), read(rr / "retrieval.json")
        assert li == ri and lw["fixture_before"] == rw["fixture_before"]
        for key in ("description", "path", "top_k"):
            assert lr["arguments"][key] == rt["arguments"][key]
        lreq, rreq = read(baseline / "wire/request-001.json"), read(rr / "wire/request-001.json")
        assert {k: v for k, v in lreq.items() if k != "messages"} == {
            k: v for k, v in rreq.items() if k != "messages"
        }
        assert (
            len(lreq["messages"]) == len(rreq["messages"]) == 2
            and lreq["messages"][0] == rreq["messages"][0]
        )
        lm, rm = lreq["messages"][1], rreq["messages"][1]
        assert (
            lm["role"] == rm["role"] == "user"
            and lm["content"].count(lr["content"]) == rm["content"].count(rt["content"]) == 1
        )
        assert lm["content"].replace(lr["content"], "<EVIDENCE>") == rm["content"].replace(
            rt["content"], "<EVIDENCE>"
        )
        assert (baseline / "workspace/.git/refs/heads/reuse-eval").read_text() == (
            rr / "workspace/.git/refs/heads/reuse-eval"
        ).read_text()
        la = next(x for x in attempts if x["attempt"] == baseline.name)
        ra = next(x for x in attempts if x["attempt"] == rr.name)
        pairs.append(
            {
                "fixture": case,
                "repeat": repeat,
                "baseline_accepted": la["accepted"],
                "repository_accepted": ra["accepted"],
                "inputs_matched_except_declared_evidence": True,
            }
        )
raw = []
for p in sorted(out.rglob("*")):
    if p.is_file() and not p.is_symlink():
        b = p.read_bytes()
        raw.append({"path": str(p.relative_to(out)), "bytes": len(b), "sha256": sha(b)})
audit = {
    "kind": "local-model-paired-audit",
    "source_commit": c.COMMIT,
    "preflight_sha256": sha((harness / "preflight-manifest.json").read_bytes()),
    "receipt_sha256": sha((out / "receipt.json").read_bytes()),
    "source_files_verified": len(source["files"]),
    "source_symlinks_verified": len(source["symlinks"]),
    "python_files_verified": len(pre["python_files"]),
    "raw_file_count": len(raw),
    "raw_files": raw,
    "attempts": attempts,
    "pairs": pairs,
    "requests": sum(x["requests"] for x in attempts),
    "usage_complete_requests": sum(x["usage_complete_requests"] for x in attempts),
    "known_prompt_tokens": sum(x["known_prompt_tokens"] for x in attempts),
    "known_completion_tokens": sum(x["known_completion_tokens"] for x in attempts),
    "interpretation": "Fixed fixture comparison only; no hosted inference. Guard denials, timeouts and finite oracle limitations remain part of the result. Shared machine and overlapping local development tests make elapsed times non-comparable as performance evidence.",
}
with path.open("x") as f:
    json.dump(audit, f, indent=2, sort_keys=True)
    f.write("\n")
print(
    json.dumps(
        {
            "audit": str(path),
            "audit_sha256": sha(path.read_bytes()),
            "receipt_sha256": audit["receipt_sha256"],
            "attempts": len(attempts),
            "pairs": len(pairs),
            "requests": audit["requests"],
            "usage_complete_requests": audit["usage_complete_requests"],
            "known_prompt_tokens": audit["known_prompt_tokens"],
            "known_completion_tokens": audit["known_completion_tokens"],
            "raw_file_count": len(raw),
        }
    )
)
