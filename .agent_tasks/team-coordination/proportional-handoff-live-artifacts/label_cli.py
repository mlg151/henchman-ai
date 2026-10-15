"""Stdlib-only CLI printing canonical labels as a JSON array."""

import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels.

    Args:
        argv: Argument list excluding the program name. When None,
            ``sys.argv[1:]`` is used.

    Returns:
        0 on success; 2 when any argument looks like an unsupported option
        (starts with ``-``), in which case an error is written to stderr and
        nothing is written to stdout.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    for arg in args:
        if arg.startswith("-"):
            print(f"unsupported option: {arg}", file=sys.stderr)
            return 2
    print(json.dumps(label_index.unique_labels(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
