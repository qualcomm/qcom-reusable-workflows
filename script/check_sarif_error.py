# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause

#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def effective_level(result: dict[str, Any], rules: list[dict[str, Any]]) -> str:
    level = result.get("level")
    if isinstance(level, str):
        return level.lower()

    rule_index = result.get("ruleIndex")
    if isinstance(rule_index, int) and 0 <= rule_index < len(rules):
        rule = rules[rule_index]
    else:
        rule_id = result.get("ruleId")
        rule = next((item for item in rules if item.get("id") == rule_id), {})

    default_configuration = rule.get("defaultConfiguration", {})
    level = default_configuration.get("level")
    return level.lower() if isinstance(level, str) else "warning"


def location_for(result: dict[str, Any]) -> tuple[str | None, int | None]:
    locations = result.get("locations", [])
    if not locations:
        return None, None

    physical_location = locations[0].get("physicalLocation", {})
    path = physical_location.get("artifactLocation", {}).get("uri")
    line = physical_location.get("region", {}).get("startLine")
    return (
        path if isinstance(path, str) else None,
        line if isinstance(line, int) else None,
    )


def annotation_value(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit_error(result: dict[str, Any]) -> None:
    rule_id = str(result.get("ruleId", "unknown-rule"))
    message_data = result.get("message", {})
    message = str(message_data.get("text", "Semgrep error-severity finding"))
    path, line = location_for(result)

    attributes = [f"title={annotation_value(rule_id)}"]
    if path:
        attributes.append(f"file={annotation_value(path)}")
    if line:
        attributes.append(f"line={line}")

    print(f"::error {','.join(attributes)}::{annotation_value(message)}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail when a SARIF file contains error-severity results."
    )
    parser.add_argument(
        "sarif_file",
        nargs="?",
        default="semgrep.sarif",
        type=Path,
        help="SARIF file to inspect (default: semgrep.sarif)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        with args.sarif_file.open(encoding="utf-8") as sarif_stream:
            sarif = json.load(sarif_stream)
    except FileNotFoundError:
        print(f"Error: SARIF file not found: {args.sarif_file}", file=sys.stderr)
        return 2
    except (OSError, json.JSONDecodeError) as error:
        print(f"Error: unable to read SARIF file: {error}", file=sys.stderr)
        return 2

    runs = sarif.get("runs")
    if not isinstance(runs, list):
        print("Error: invalid SARIF file: 'runs' must be an array", file=sys.stderr)
        return 2

    error_results: list[dict[str, Any]] = []
    for run in runs:
        if not isinstance(run, dict):
            print("Error: invalid SARIF file: each run must be an object", file=sys.stderr)
            return 2

        driver = run.get("tool", {}).get("driver", {})
        rules = driver.get("rules", [])
        results = run.get("results", [])
        if not isinstance(rules, list) or not isinstance(results, list):
            print(
                "Error: invalid SARIF file: 'rules' and 'results' must be arrays",
                file=sys.stderr,
            )
            return 2

        for result in results:
            if not isinstance(result, dict):
                print(
                    "Error: invalid SARIF file: each result must be an object",
                    file=sys.stderr,
                )
                return 2
            if effective_level(result, rules) == "error":
                error_results.append(result)

    if error_results:
        for result in error_results:
            emit_error(result)
        print(f"Found {len(error_results)} error-severity finding(s).", file=sys.stderr)
        return 1

    print("No error-severity findings found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
