"""Check one fixed fixture without importing or executing its candidate source."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import fixtures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=fixtures.CASES)
    args = parser.parse_args()
    result = fixtures.oracle(Path.cwd(), args.case)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result['accepted'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
