"""Stdlib-only CLI printing unique normalized labels as a JSON array."""

import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels.

    Accepts positional labels only. Any argument starting with ``-`` is an
    unsupported option: a short message goes to stderr and the exit status
    is 2 without printing the JSON array.

    Args:
        argv: Argument list excluding the program name; defaults to
            ``sys.argv[1:]``.

    Returns:
        Exit status: 0 on success, 2 on any unsupported option.
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
