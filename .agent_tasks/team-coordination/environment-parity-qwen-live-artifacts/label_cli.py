"""CLI wrapper for label_index.unique_labels."""

import argparse
import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels."""
    parser = argparse.ArgumentParser(
        description="Print unique normalized labels as JSON"
    )
    parser.add_argument("labels", nargs="*", help="Labels to normalize and deduplicate")
    args = parser.parse_args(argv)

    labels = label_index.unique_labels(args.labels)
    print(json.dumps(labels))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
