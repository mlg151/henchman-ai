"""Print a JSON array of unique normalized positional labels."""

import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print unique normalized positional labels as a JSON array.

    The CLI accepts no options: any argument starting with ``-`` is treated as
    an unsupported option. Remaining arguments are positional labels passed to
    ``label_index.unique_labels``.

    Args:
        argv: Command-line arguments excluding the program name. When ``None``,
            ``sys.argv[1:]`` is used.

    Returns:
        0 on success; 2 when an unsupported option is supplied.
    """
    if argv is None:
        argv = sys.argv[1:]
    labels: list[str] = []
    for arg in argv:
        if arg.startswith("-"):
            print(f"unsupported option: {arg}", file=sys.stderr)
            return 2
        labels.append(arg)
    print(json.dumps(label_index.unique_labels(labels)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
