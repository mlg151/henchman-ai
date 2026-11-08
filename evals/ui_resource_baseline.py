"""Opt-in headless transcript resource observations; no model or native paint claim.

Run each parameter in a fresh pytest process using the documented command in
docs/evaluations/2026-11-08-ui-resource-baseline.md. Normal pytest collection
does not include this file. The offline fixture isolates settings and transports.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest
from tests.cli.ui_scenarios import InteractionApp, settle_layout

from henchman.cli import textual_app
from henchman.cli.textual_widgets import ChatPane

pytest_plugins = ["tests.offline_network"]
WORKLOAD_VERSION = "UI-RESOURCE-0.1"
CASES = [(width, height, count) for width, height in ((80, 24), (120, 40), (160, 50)) for count in (40, 1000)]


def _memory() -> dict[str, int]:
    """Read this process's Linux resident/private-share observations in KiB."""
    fields = {}
    for line in Path("/proc/self/smaps_rollup").read_text().splitlines():
        key, _, value = line.partition(":")
        if key in {"Rss", "Pss", "Private_Clean", "Private_Dirty", "Swap"}:
            fields[key + "_kib"] = int(value.split()[0])
    return fields


@pytest.mark.parametrize("width,height,count", CASES, ids=[f"{w}x{h}-{n}" for w, h, n in CASES])
async def test_headless_transcript_resources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, width: int, height: int, count: int,
) -> None:
    """Observe resources without making timing or native usability assertions."""
    destination = os.environ.get("HENCHMAN_UI_RESOURCE_OUTPUT")
    if destination is None or platform.system() != "Linux":
        pytest.skip("Explicit output directory and Linux smaps_rollup required")
    output = Path(destination)
    assert output.is_absolute() and output.is_dir()
    module = Path(textual_app.__file__).resolve()
    checkout = module.parents[3]
    revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    assert revision == os.environ["HENCHMAN_UI_RESOURCE_REVISION"]
    monkeypatch.chdir(tmp_path)
    app = InteractionApp(tmp_path)
    import resource
    from importlib.metadata import version

    report: dict[str, Any] = {
        "workload_version": WORKLOAD_VERSION,
        "revision": revision,
        "runtime_module_sha256": hashlib.sha256(module.read_bytes()).hexdigest(),
        "python": platform.python_version(), "textual": version("textual"),
        "os": platform.platform(), "terminal": "Textual headless driver; no emulator",
        "cpu": next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")),
        "host_memory_kib": int(Path("/proc/meminfo").read_text().splitlines()[0].split()[1]),
        "host_load_1_5_15": os.getloadavg(),
        "dimensions": [width, height], "history_messages": count,
        "mode": "rich/default density/default motion; idle empty focused composer",
        "idle_seconds_requested": 5,
        "limitations": ["No input-to-paint or visible cancellation measurement", "No terminal/clipboard/IME/AT/user qualification", "Shared host, no affinity or load isolation", "One observation per fresh process, not a statistical comparison"],
    }
    async with app.run_test(size=(width, height)) as pilot:
        await settle_layout(pilot)
        report["before_history"] = _memory()
        chat = app.query_one(ChatPane)
        started, cpu_started = time.perf_counter(), time.process_time()
        for number in range(count):
            chat.add_user_message(f"History {number}: café /workspace/long-directory-name/module_{number}.py " + "readable text " * 8)
        await settle_layout(pilot)
        report["history_load_wall_seconds"] = time.perf_counter() - started
        report["history_load_cpu_seconds"] = time.process_time() - cpu_started
        assert len(chat.children) == count
        assert app.query_one("#input").region.bottom <= height
        report["after_history"] = _memory()
        started, cpu_started = time.perf_counter(), time.process_time()
        await asyncio.sleep(5)
        report["idle_wall_seconds"] = time.perf_counter() - started
        report["idle_cpu_seconds"] = time.process_time() - cpu_started
        report["idle_cpu_one_core_percent"] = 100 * report["idle_cpu_seconds"] / report["idle_wall_seconds"]
        report["after_idle"] = _memory()
        report["peak_rss_kib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        assert not app.submitted
    report["after_unmount"] = _memory()
    report["status"] = "observed"
    (output / f"{width}x{height}-{count}.json").write_text(json.dumps(report, indent=2) + "\n")
