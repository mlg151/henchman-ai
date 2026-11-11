"""Compare synthetic unmounted widget lifetimes in an isolated process."""

from __future__ import annotations

import argparse
import gc
import importlib.metadata
import json
import platform
import sys
import weakref
from pathlib import Path
from typing import Any


def observe(widget_type: type[Any], *, weak_nodes: bool) -> dict[str, Any]:
    """Count weakly observed widgets before and after an explicit collection."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    references: list[weakref.ReferenceType[Any]] = []
    changed_identity = 0
    try:
        for index in range(100):
            widget = widget_type("User:", f"synthetic {index}")
            styles = (widget._css_styles, widget._inline_styles, widget.styles)
            if not all(style.node is widget for style in styles):
                raise RuntimeError("Unexpected Textual style ownership")
            if weak_nodes:
                for style in styles:
                    style.node = weakref.proxy(widget)
                changed_identity += sum(style.node is not widget for style in styles)
                widget.set_content(f"updated synthetic {index}")
                del style
            references.append(weakref.ref(widget))
            del styles, widget
        before = sum(reference() is not None for reference in references)
        collected = gc.collect()
        after = sum(reference() is not None for reference in references)
        return {"widgets": len(references), "alive_before_collect": before,
                "alive_after_collect": after, "collected_objects": collected,
                "style_node_identity_changes": changed_identity}
    finally:
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
    receipt = {
        "python": platform.python_version(),
        "textual": importlib.metadata.version("textual"),
        "source": str(source),
        "widget_module": str(Path(module_file).resolve()),
        "normal": observe(ChatMessage, weak_nodes=False),
        "weak_node_experiment": observe(ChatMessage, weak_nodes=True),
        "limitations": ["Synthetic unmounted widgets only", "One process and one Textual version",
                        "Private Textual attributes and weak proxies change object identity",
                        "No production behavior or performance was tested"],
    }
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(receipt, output, indent=2)
        output.write("\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
