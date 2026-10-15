"""Command-line interface printing unique normalized labels as JSON."""

import argparse
import json

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels.

    Args:
        argv: Argument list to parse; defaults to ``sys.argv[1:]``.

    Returns:
        Exit status: 0 on success. Unsupported options exit with status 2
        via argparse's default error behavior.
    """
    parser = argparse.ArgumentParser(
        description="Print unique normalized labels as a JSON array."
    )
    parser.add_argument("labels", nargs="*", help="Raw labels to normalize and dedupe")
    args = parser.parse_args(argv)
    print(json.dumps(label_index.unique_labels(args.labels)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
