# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause

#!/usr/bin/env python3

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests



def get_effective_level(result: Dict[str, Any], rules: List[Dict[str, Any]]) -> str:
    """Extract the severity level from a SARIF result."""
    level = result.get("level")
    if isinstance(level, str):
        return level.lower()

    # Look up level from rule definition
    rule_index = result.get("ruleIndex")
    if isinstance(rule_index, int) and 0 <= rule_index < len(rules):
        rule = rules[rule_index]
    else:
        rule_id = result.get("ruleId")
        rule = next((r for r in rules if r.get("id") == rule_id), {})

    level = rule.get("defaultConfiguration", {}).get("level")
    return level.lower() if isinstance(level, str) else "warning"


def get_location(result: Dict[str, Any]) -> Tuple[Optional[str], Optional[int]]:
    """Extract file path and line number from a SARIF result."""
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


def print_finding(data: Dict[str, Any], is_github_alert: bool = False) -> None:
    """Print a formatted error message for a SARIF result or GitHub alert."""
    if is_github_alert:
        # GitHub API alert format
        rule_id = data.get("rule", {}).get("id", "unknown-rule")
        most_recent = data.get("most_recent_instance", {})
        message = most_recent.get("message", {}).get("text", "Semgrep error-severity finding")
        location_data = most_recent.get("location", {})
        path = location_data.get("path")
        line = location_data.get("start_line")
        alert_url = data.get("html_url")
    else:
        # SARIF format
        rule_id = data.get("ruleId", "unknown-rule")
        message = data.get("message", {}).get("text", "Semgrep error-severity finding")
        path, line = get_location(data)
        alert_url = None
    
    location = f"{path}:{line}" if path and line else path if path else "unknown location"
    
    print(f"ERROR: {location}", file=sys.stderr)
    print(f"  Rule: {rule_id}", file=sys.stderr)
    print(f"  Message: {message}", file=sys.stderr)
    if alert_url:
        print(f"  Alert URL: {alert_url}", file=sys.stderr)
    print("", file=sys.stderr)


NO_ADVANCED_SECURITY_MESSAGE = "Advanced Security must be enabled"


class CodeScanningUnavailable(Exception):
    """Raised when GitHub code scanning is not enabled (internal/private repo without GHAS)."""


MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def get_with_retry(url: str, headers: Dict[str, str], params: Dict[str, str]) -> requests.Response:
    """
    GET with exponential backoff on connection errors, timeouts and transient HTTP statuses.
    Raises requests.RequestException once all attempts are exhausted.
    """
    attempt = 1
    while True:
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code not in RETRYABLE_STATUS_CODES:
                return resp
            if attempt == MAX_ATTEMPTS:
                resp.raise_for_status()  # raises HTTPError for 429/5xx
            reason = f"HTTP {resp.status_code}"
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == MAX_ATTEMPTS:
                raise
            reason = str(e)

        delay = RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1)
        print(
            f"Request failed ({reason}); retrying in {delay}s (attempt {attempt}/{MAX_ATTEMPTS})",
            file=sys.stderr,
        )
        time.sleep(delay)
        attempt += 1


def fetch_open_alerts(owner: str, repo: str, token: str, ref: str) -> List[Dict[str, Any]]:
    """
    Fetch open code-scanning alerts from GitHub.
    Returns a list of alert objects.
    Raises CodeScanningUnavailable if the repo has no Advanced Security.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/code-scanning/alerts"

    # Build query parameters
    params = {
        "state": "open",
        "tool_name": "Semgrep OSS",
        "severity": "error",
        "per_page": "100",
        "ref": ref,
    }

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    
    all_alerts: List[Dict[str, Any]] = []
    page = 1
    
    while True:
        # Add page parameter for pagination
        params["page"] = str(page)

        resp = get_with_retry(url, headers, params)
        if resp.status_code == 403 and NO_ADVANCED_SECURITY_MESSAGE in resp.text:
            raise CodeScanningUnavailable(resp.json().get("message", ""))
        resp.raise_for_status()
        alerts = resp.json()
        if not isinstance(alerts, list):
            raise ValueError(f"Unexpected response from code-scanning API: {alerts!r}")

        # Collect all alert objects
        all_alerts.extend(alerts)
        
        # Check if there are more pages
        if len(alerts) < 100:
            break
        page += 1
    
    return all_alerts


def load_sarif(file_path: Path) -> Dict[str, Any]:
    """Load and validate SARIF file."""
    try:
        with file_path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: SARIF file not found: {file_path}", file=sys.stderr)
        sys.exit(2)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Error: Unable to read SARIF file: {e}", file=sys.stderr)
        sys.exit(2)


def extract_error_results(sarif: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract all error-severity results from SARIF."""
    runs = sarif.get("runs")
    if not isinstance(runs, list):
        print("Error: Invalid SARIF file: 'runs' must be an array", file=sys.stderr)
        sys.exit(2)

    error_results = []
    
    for run in runs:
        if not isinstance(run, dict):
            print("Error: Invalid SARIF file: each run must be an object", file=sys.stderr)
            sys.exit(2)

        rules = run.get("tool", {}).get("driver", {}).get("rules", [])
        results = run.get("results", [])
        
        if not isinstance(rules, list) or not isinstance(results, list):
            print("Error: Invalid SARIF file: 'rules' and 'results' must be arrays", file=sys.stderr)
            sys.exit(2)

        for result in results:
            if not isinstance(result, dict):
                print("Error: Invalid SARIF file: each result must be an object", file=sys.stderr)
                sys.exit(2)
            
            if get_effective_level(result, rules) == "error":
                error_results.append(result)

    return error_results


def main() -> int:
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
    args = parser.parse_args()

    # Load and parse SARIF file
    sarif = load_sarif(args.sarif_file)
    error_results = extract_error_results(sarif)

    # Get GitHub context from environment
    github_repository = os.environ.get("GITHUB_REPOSITORY", "")
    github_ref = os.environ.get("GITHUB_REF", "")
    github_token = os.environ.get("GITHUB_TOKEN")

    # Parse repository owner and name
    if "/" not in github_repository:
        print("Warning: Invalid GITHUB_REPOSITORY format", file=sys.stderr)
        owner, repo = "", ""
    else:
        owner, repo = github_repository.split("/", 1)

    ref = github_ref or ""
    if ref.startswith("refs/pull/") and ref.endswith("/merge"):
            ref = ref.rsplit("/", 1)[0] + "/head"
    # Use GitHub alert state when code scanning is available; otherwise fall back
    # to SARIF parsing (internal/private repos without Advanced Security).
    open_alerts: Optional[List[Dict[str, Any]]] = None
    if not (owner and repo and github_token and ref):
        print("Missing GitHub context (repository/token/ref); using SARIF-only check", file=sys.stderr)
    else:
        try:
            print(f"Fetching open alerts for {owner}/{repo} on ref: {ref}", file=sys.stderr)
            open_alerts = fetch_open_alerts(owner, repo, github_token, ref)
        except CodeScanningUnavailable as e:
            print(f"Code scanning unavailable ({e}); using SARIF-only check", file=sys.stderr)
        except (requests.RequestException, ValueError) as e:
            print(f"Error: Unable to fetch GitHub alerts: {e}", file=sys.stderr)
            return 2

    if open_alerts is not None:
        if open_alerts:
            print(f"Found {len(open_alerts)} open alert(s) on GitHub", file=sys.stderr)
            for alert in open_alerts:
                print_finding(alert, is_github_alert=True)
            print(f"Found {len(open_alerts)} error-severity finding(s) from GitHub alerts.", file=sys.stderr)
            return 1
        print("No error-severity findings matching open GitHub alerts.")
        return 0

    print("Using SARIF-only check (all error-severity findings will fail)", file=sys.stderr)
    if error_results:
        for result in error_results:
            print_finding(result)
        print(f"Found {len(error_results)} error-severity finding(s).", file=sys.stderr)
        return 1
    print("No error-severity findings found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
