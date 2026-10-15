"""CLI for unique label processing."""

from __future__ import annotations

import json
import sys
from typing import Sequence

import label_index


def main(argv: Sequence[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(json.dumps([]))
        return 0

    # Check for unsupported options (flags starting with -)
    for arg in argv:
        if arg.startswith("-"):
            print(json.dumps([]), file=sys.stderr)
            return 2

    labels = label_index.unique_labels(list(argv))
    print(json.dumps(labels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
