"""Stdlib-only CLI printing unique normalized labels as a JSON array."""

import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels.

    Args:
        argv: Arguments excluding the program name; defaults to
            ``sys.argv[1:]``.

    Returns:
        0 on success, 2 if any unsupported option (token starting with
        ``-``) is supplied.
    """
    args = sys.argv[1:] if argv is None else argv
    for token in args:
        if token.startswith("-"):
            print(f"unrecognized option: {token}", file=sys.stderr)
            return 2
    print(json.dumps(label_index.unique_labels(args)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
