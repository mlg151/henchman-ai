import json
import sys

import label_index


def main(argv: list[str] | None = None) -> int:
    """Print a JSON array of unique normalized positional labels."""
    labels = argv if argv is not None else sys.argv[1:]
    result = label_index.unique_labels(labels)
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
