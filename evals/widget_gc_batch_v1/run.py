"""Inspect synthetic transcript widget lifetimes under explicit GC batches."""

from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import platform
import sys
import weakref
from collections import deque
from pathlib import Path
from typing import Any


def observe(widget_type: type[Any], generation: int | None) -> dict[str, Any]:
    """Keep the newest 128 of 1,000 widgets and inspect older weak references."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    retained: deque[Any] = deque()
    references: list[weakref.ReferenceType[Any]] = []
    collections = 0
    collected = 0
    evictions = 0
    try:
        for index in range(1000):
            widget = widget_type("User:", f"synthetic {index}")
            retained.append(widget)
            references.append(weakref.ref(widget))
            if len(retained) > 128:
                retained.popleft()
                evictions += 1
                if generation is not None and evictions % 32 == 0:
                    collected += gc.collect(generation)
                    collections += 1
            del widget
        old_alive = sum(reference() is not None for reference in references[:-128])
        retained_alive = sum(reference() is not None for reference in references[-128:])
        retained.clear()
        gc.collect()
        after_cleanup = sum(reference() is not None for reference in references)
        return {"generation": generation, "evicted": evictions,
                "evicted_alive_before_cleanup": old_alive,
                "retained_alive_before_cleanup": retained_alive,
                "collections": collections, "collected_objects": collected,
                "alive_after_cleanup": after_cleanup}
    finally:
        retained.clear()
        gc.collect()
        if was_enabled:
            gc.enable()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    sys.path.insert(0, str(source / "src"))
    from henchman.cli.textual_widgets import ChatMessage

    module_file = sys.modules[ChatMessage.__module__].__file__
    if module_file is None:
        raise RuntimeError("Widget module path unavailable")
    receipt = {"python": platform.python_version(), "textual": importlib.metadata.version("textual"),
               "source": str(source), "widget_module": str(Path(module_file).resolve()),
               "arms": [observe(ChatMessage, generation) for generation in (None, 0, 1, 2)],
               "limitations": ["Synthetic unmounted widgets, not a running transcript",
                               "Automatic GC disabled; sequential arms in one process",
                               "Explicit collection runs global finalizers and is not a proposed production policy",
                               "No latency, native display, model or user evidence"]}
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(receipt, output, indent=2)
        output.write("\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
