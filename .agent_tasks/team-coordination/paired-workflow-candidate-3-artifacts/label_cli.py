import json
import sys
from typing import List

import label_index


def main(argv: List[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels."""
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print(json.dumps([]))
        return 0

    if any(arg.startswith("-") for arg in argv):
        print(json.dumps([]))
        return 2

    labels = label_index.unique_labels(argv)
    print(json.dumps(labels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
