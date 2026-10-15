import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels."""
    if argv is None:
        argv = sys.argv[1:]
    
    # Check for unsupported options (flags starting with -)
    for arg in argv:
        if arg.startswith("-"):
            return 2
    
    labels = label_index.unique_labels(argv)
    print(json.dumps(labels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
