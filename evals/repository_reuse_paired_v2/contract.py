"""Versioned paired comparison contract; no endpoint I/O at import or in plan."""

from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "source"
COMMIT = "d195ac18d3c2d586e30f29f218c7813e97c97269"
ENDPOINT = "http://127.0.0.1:8081/v1"
MODEL = "qwen38-27b-iq3s"
KEY = "local-paired-experiment-no-hosted-credential"
ATTEMPT_SECONDS = 450
CLEANUP_SECONDS = 30
REQUESTS = 12
OUTPUT = 4096
CONTEXT = 32768
INPUT = 27852
RAW_LIMIT = 2 * 1024 * 1024
VERSION = "repository-evidence-paired-v2"


class Denied(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def require_target(endpoint, model):
    if endpoint != ENDPOINT or model != MODEL:
        raise Denied("Exact reviewed local endpoint and model required")


def settings_data():
    return {
        "providers": {
            "default": "openai_compat",
            "openai_compat": {
                "api_key": KEY,
                "base_url": ENDPOINT,
                "model": MODEL,
                "temperature": 0,
                "max_tokens": OUTPUT,
            },
        },
        "context": {"max_tokens": CONTEXT, "compaction_threshold": 0.85, "auto_compact": False},
        "agents": {
            "max_delegation_retries": 0,
            "max_delegation_turns": 10,
            "agents": {
                "engineer": {
                    "name": "Comparison engineer",
                    "role": "engineer",
                    "description": "Reuse existing helpers in the held repository fixture",
                    "tools": ["read_file", "edit_file", "write_file", "verify_plan_execution", "pattern_search"],
                }
            },
        },
        "usage": {
            "persistence": "process",
            "limits": {"max_requests": REQUESTS, "max_seconds": ATTEMPT_SECONDS},
        },
        "operations": {"persistence": "process"},
    }


def plan():
    from fixtures import CASES, fixture_manifest

    rows = []
    for case in CASES:
        for repeat in (1, 2):
            for arm in ("baseline", "repository") if repeat == 1 else ("repository", "baseline"):
                rows.append(
                    {
                        "attempt_id": f"{case}-{repeat}-{arm}",
                        "fixture": case,
                        "repeat": repeat,
                        "arm": arm,
                    }
                )
    return {
        "version": VERSION,
        "source_commit": COMMIT,
        "endpoint": ENDPOINT,
        "model": MODEL,
        "attempts": rows,
        "settings": settings_data(),
        "settings_sha256": digest(json_bytes(settings_data())),
        "fixtures": fixture_manifest(),
        "bounds": {
            "attempt_seconds": ATTEMPT_SECONDS,
            "cleanup_seconds": CLEANUP_SECONDS,
            "requests": REQUESTS,
            "tool_rounds": 10,
            "preparation_retrievals": 1,
            "query_top_k": 5,
            "output_tokens": OUTPUT,
            "context_tokens": CONTEXT,
            "serialized_input_budget": INPUT,
            "SDK_retries": 0,
            "delegation_retries": 0,
        },
        "interpretation": "Separate supplied-evidence helper reuse comparison, not canonical recovery-corpus qualification. Independent current-byte oracle determines acceptance; scoped_pass does not. Two repeats do not establish reliability. Ties establish no improvement. Warm shared server; no hardware/physical-cold/CPU claims.",
    }


def verify_source():
    manifest = json.loads((HERE / "source-manifest.json").read_text())
    if manifest["commit"] != COMMIT:
        raise Denied("Source commit mismatch")
    for name, sha in manifest["files"].items():
        path = SOURCE / name
        if path.is_symlink() and (
            manifest.get("symlinks", {}).get(name) != os.readlink(path)
            or not path.resolve().is_relative_to(SOURCE)
        ):
            raise Denied("Source link mismatch")
        if not path.is_file() or digest(path.read_bytes()) != sha:
            raise Denied("Source snapshot mismatch")
    import henchman

    if not Path(henchman.__file__).resolve().is_relative_to(SOURCE):
        raise Denied("Source import escaped snapshot")
    return {
        "commit": COMMIT,
        "manifest_sha256": digest((HERE / "source-manifest.json").read_bytes()),
    }


def environment(root, executable):
    root = Path(root)
    for name in ("home", "tmp", "cache", "data", "config"):
        (root / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    return {
        "HOME": str(root / "home"),
        "USERPROFILE": str(root / "home"),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_DATA_HOME": str(root / "data"),
        "TMPDIR": str(root / "tmp"),
        "PATH": str(Path(executable).parent) + ":/usr/bin:/bin",
        "PYTHONPATH": str(HERE) + os.pathsep + str(SOURCE / "src"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PIP_NO_INDEX": "1",
        "UV_OFFLINE": "1",
        "UV_NO_CONFIG": "1",
        "UV_PYTHON_DOWNLOADS": "never",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "TERM": "dumb",
    }


if __name__ == "__main__":
    print(json.dumps(plan(), indent=2))
