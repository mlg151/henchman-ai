"""CLI for unique_labels: prints JSON array of normalized unique labels."""

import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels."""
    if argv is None:
        argv = sys.argv[1:]

    # Reject unsupported options (anything starting with -)
    if any(arg.startswith("-") for arg in argv):
        return 2

    result = label_index.unique_labels(argv)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
