# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause

#!/usr/bin/env python3

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# False positive: never block the check for these rules.
NON_BLOCKING_RULES = {"python.lang.security.use-defused-xml-parse.use-defused-xml-parse"}


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


def clean(value: Any) -> str:
    """Flatten control characters so scanned-repo text cannot start a workflow command line."""
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(value))


def print_finding(data: Dict[str, Any], is_github_alert: bool = False) -> None:
    """Print a formatted error message for a SARIF result or GitHub alert."""
    if is_github_alert:
        # GitHub API alert format
        rule_id = data.get("rule", {}).get("id", "unknown-rule")
        most_recent = data.get("most_recent_instance", {})
        message = most_recent.get("message", {}).get("text", "error-severity finding")
        location_data = most_recent.get("location", {})
        path = location_data.get("path")
        line = location_data.get("start_line")
        alert_url = data.get("html_url")
    else:
        # SARIF format
        rule_id = data.get("ruleId", "unknown-rule")
        message = data.get("message", {}).get("text", "error-severity finding")
        path, line = get_location(data)
        alert_url = None
    
    location = f"{path}:{line}" if path and line else path if path else "unknown location"
    
    print(f"ERROR: {clean(location)}", file=sys.stderr)
    print(f"  Rule: {clean(rule_id)}", file=sys.stderr)
    print(f"  Message: {clean(message)}", file=sys.stderr)
    if alert_url:
        print(f"  Alert URL: {clean(alert_url)}", file=sys.stderr)
    print("", file=sys.stderr)


NO_ADVANCED_SECURITY_MESSAGE = "Advanced Security must be enabled"


class CodeScanningUnavailable(Exception):
    """Raised when GitHub code scanning is not enabled (internal/private repo without GHAS)."""


class ApiRequestError(Exception):
    """Raised when the GitHub API request fails or returns an error status."""


MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 2
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class _AuthSafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow redirects, but send the token only to the same scheme and host, like requests."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_request = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_request is not None:
            old, new = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(new_request.full_url)
            if (old.scheme, old.netloc) != (new.scheme, new.netloc):
                new_request.remove_header("Authorization")
        return new_request


_OPENER = urllib.request.build_opener(_AuthSafeRedirectHandler)


def get_with_retry(url: str, headers: Dict[str, str], params: Dict[str, str]) -> Tuple[int, str]:
    """
    GET with exponential backoff on connection errors, timeouts and transient HTTP statuses.
    Returns the HTTP status and response body.
    Raises ApiRequestError once all attempts are exhausted.
    """
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}", headers=headers)
    attempt = 1
    while True:
        try:
            try:
                with _OPENER.open(request, timeout=30) as resp:
                    status, body = resp.status, resp.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                status, body = e.code, e.read().decode("utf-8", errors="replace")
            if status not in RETRYABLE_STATUS_CODES:
                return status, body
            reason = f"HTTP {status}"
        except (OSError, http.client.HTTPException) as e:
            # OSError covers URLError, timeouts and connection resets.
            reason = str(e)

        if attempt == MAX_ATTEMPTS:
            raise ApiRequestError(f"{reason} after {MAX_ATTEMPTS} attempts")

        delay = RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1)
        print(
            f"Request failed ({reason}); retrying in {delay}s (attempt {attempt}/{MAX_ATTEMPTS})",
            file=sys.stderr,
        )
        time.sleep(delay)
        attempt += 1


def fetch_open_alerts(owner: str, repo: str, token: str, ref: str, tool_name: str) -> List[Dict[str, Any]]:
    """
    Fetch open error-severity code-scanning alerts of a tool from GitHub.
    Returns a list of alert objects.
    Raises CodeScanningUnavailable if the repo has no Advanced Security.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/code-scanning/alerts"

    # Severity is filtered client-side: the API's severity=error filter skips
    # alerts whose rule sets a security-severity (those match critical/high/...).
    params = {
        "state": "open",
        "tool_name": tool_name,
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

        status, body = get_with_retry(url, headers, params)
        if status == 403 and NO_ADVANCED_SECURITY_MESSAGE in body:
            raise CodeScanningUnavailable(json.loads(body).get("message", ""))
        if status != 200:
            raise ApiRequestError(f"HTTP {status}: {body[:200]}")
        alerts = json.loads(body)
        if not isinstance(alerts, list):
            raise ValueError(f"Unexpected response from code-scanning API: {alerts!r}")

        # Collect all alert objects
        all_alerts.extend(alerts)
        
        # Check if there are more pages
        if len(alerts) < 100:
            break
        page += 1
    
    return [a for a in all_alerts if a.get("rule", {}).get("severity") == "error"]


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
    parser.add_argument(
        "--tool-name",
        default="Semgrep OSS",
        help='Code scanning tool whose open GitHub alerts are checked (default: "Semgrep OSS")',
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
            print(f"Fetching open {args.tool_name} alerts for {owner}/{repo} on ref: {ref}", file=sys.stderr)
            open_alerts = fetch_open_alerts(owner, repo, github_token, ref, args.tool_name)
        except CodeScanningUnavailable as e:
            print(f"Code scanning unavailable ({e}); using SARIF-only check", file=sys.stderr)
        except (ApiRequestError, ValueError) as e:
            print(f"Error: Unable to fetch GitHub alerts: {e}", file=sys.stderr)
            return 2

    if open_alerts is not None:
        open_alerts = [a for a in open_alerts if a.get("rule", {}).get("id") not in NON_BLOCKING_RULES]
        if open_alerts:
            print(f"Found {len(open_alerts)} open alert(s) on GitHub", file=sys.stderr)
            for alert in open_alerts:
                print_finding(alert, is_github_alert=True)
            print(f"Found {len(open_alerts)} error-severity finding(s) from GitHub alerts.", file=sys.stderr)
            return 1
        print("No error-severity findings matching open GitHub alerts.")
        return 0

    print("Using SARIF-only check (all error-severity findings will fail)", file=sys.stderr)
    error_results = [r for r in error_results if r.get("ruleId") not in NON_BLOCKING_RULES]
    if error_results:
        for result in error_results:
            print_finding(result)
        print(f"Found {len(error_results)} error-severity finding(s).", file=sys.stderr)
        return 1
    print("No error-severity findings found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
