# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause

#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict


def filter_suppressed(sarif: Dict[str, Any]) -> int:
    """Drop suppressed results from every run in place. Returns the count dropped."""
    dropped = 0

    runs = sarif.get("runs")
    if not isinstance(runs, list):
        return dropped

    for run in runs:
        if not isinstance(run, dict):
            continue

        results = run.get("results")
        if not isinstance(results, list):
            continue

        kept = [result for result in results if not result.get("suppressions")]
        dropped += len(results) - len(kept)
        run["results"] = kept

    return dropped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Drop SARIF results carrying an in-source 'suppressions' entry "
            "(e.g. nosemgrep) before upload, since GitHub code scanning "
            "otherwise still opens an alert for them."
        )
    )
    parser.add_argument(
        "sarif_file",
        nargs="?",
        default="semgrep.sarif",
        type=Path,
        help="SARIF file to filter (default: semgrep.sarif)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Where to write the filtered SARIF (default: overwrite sarif_file)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output or args.sarif_file

    try:
        with args.sarif_file.open(encoding="utf-8") as sarif_stream:
            sarif = json.load(sarif_stream)
    except FileNotFoundError:
        print(f"Error: SARIF file not found: {args.sarif_file}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as error:
        print(f"Error: unable to read SARIF file: {error}", file=sys.stderr)
        return 2

    dropped = filter_suppressed(sarif)

    with output.open("w", encoding="utf-8") as sarif_stream:
        json.dump(sarif, sarif_stream)

    print(f"Dropped {dropped} suppressed result(s) from {output}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
