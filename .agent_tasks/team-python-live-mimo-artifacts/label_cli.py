"""Print a JSON array of unique normalized positional labels."""

import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels.

    Args:
        argv: Command-line arguments; defaults to ``sys.argv[1:]``.

    Returns:
        0 on success; 2 if any argument is an unsupported option.
    """
    args: list[str] = sys.argv[1:] if argv is None else argv
    for arg in args:
        if arg.startswith("-"):
            print(f"unsupported option: {arg}", file=sys.stderr)
            return 2
    print(json.dumps(label_index.unique_labels(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
