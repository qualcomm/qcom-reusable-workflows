# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# SPDX-License-Identifier: BSD-3-Clause

"""Unit tests for check_sarif_error.py. Run with: python3 -m unittest discover -s script"""

import contextlib
import http.server
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_sarif_error as c  # noqa: E402


def sarif(results, rules=None):
    return {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "t", "rules": rules or []}}, "results": results}]}


def alert(rule_id="r1", severity="error"):
    return {
        "rule": {"id": rule_id, "severity": severity},
        "most_recent_instance": {"message": {"text": "m"}, "location": {"path": "a.txt", "start_line": 1}},
        "html_url": "https://example.invalid/1",
    }


class EffectiveLevelTest(unittest.TestCase):
    def test_result_level_wins(self):
        rules = [{"id": "r", "defaultConfiguration": {"level": "warning"}}]
        self.assertEqual(c.get_effective_level({"level": "ERROR", "ruleIndex": 0}, rules), "error")

    def test_falls_back_to_rule_by_index_then_id(self):
        rules = [{"id": "r", "defaultConfiguration": {"level": "error"}}]
        self.assertEqual(c.get_effective_level({"ruleIndex": 0}, rules), "error")
        self.assertEqual(c.get_effective_level({"ruleId": "r"}, rules), "error")

    def test_defaults_to_warning(self):
        self.assertEqual(c.get_effective_level({"ruleId": "unknown"}, []), "warning")


class ExtractErrorResultsTest(unittest.TestCase):
    def test_keeps_only_errors(self):
        results = [{"ruleId": "a", "level": "error"}, {"ruleId": "b", "level": "warning"}, {"ruleId": "c", "level": "note"}]
        self.assertEqual([r["ruleId"] for r in c.extract_error_results(sarif(results))], ["a"])

    def test_invalid_sarif_exits_2(self):
        for bad in ({"runs": {}}, {"runs": ["x"]}, {"runs": [{"results": {}}]}, {"runs": [{"results": ["x"]}]}):
            with self.subTest(bad=bad), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    c.extract_error_results(bad)
                self.assertEqual(cm.exception.code, 2)


class CleanTest(unittest.TestCase):
    def test_no_line_can_start_a_workflow_command(self):
        out = c.clean("pkg\n::error::spoofed\r\n::stop-commands::x\x1b[31m")
        self.assertNotIn("\n", out)
        self.assertNotIn("\r", out)
        self.assertNotIn("\x1b", out)


class FetchOpenAlertsTest(unittest.TestCase):
    def fetch(self, responses):
        calls = []

        def fake(url, headers, params):
            calls.append(dict(params))
            return responses[len(calls) - 1]

        with mock.patch.object(c, "get_with_retry", side_effect=fake):
            return c.fetch_open_alerts("o", "r", "tok", "refs/heads/main", "omni-audit"), calls

    def test_paginates_and_keeps_only_error_severity(self):
        page1 = [alert(severity="error")] * 100
        page2 = [alert(severity="warning"), alert(severity="note"), alert(severity="error")]
        alerts, calls = self.fetch([(200, json.dumps(page1)), (200, json.dumps(page2))])
        self.assertEqual(len(alerts), 101)
        self.assertEqual([p["page"] for p in calls], ["1", "2"])

    def test_queries_tool_name_without_server_side_severity_filter(self):
        # severity=error on the API skips alerts whose rule has a security-severity.
        _, calls = self.fetch([(200, "[]")])
        self.assertEqual(calls[0]["tool_name"], "omni-audit")
        self.assertNotIn("severity", calls[0])

    def test_missing_advanced_security_raises_unavailable(self):
        body = json.dumps({"message": "Advanced Security must be enabled for this repository to use code scanning."})
        with self.assertRaises(c.CodeScanningUnavailable):
            self.fetch([(403, body)])

    def test_error_status_and_bad_payload_raise(self):
        with self.assertRaises(c.ApiRequestError):
            self.fetch([(404, '{"message": "Not Found"}')])
        with self.assertRaises(ValueError):
            self.fetch([(200, '{"not": "a list"}')])
        with self.assertRaises(ValueError):
            self.fetch([(200, "not json")])


class _Handler(http.server.BaseHTTPRequestHandler):
    statuses = []
    seen = []

    def do_GET(self):
        _Handler.seen.append((self.path, self.headers.get("Authorization")))
        status = _Handler.statuses.pop(0) if _Handler.statuses else 200
        body = b"[]" if status == 200 else b"{}"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class GetWithRetryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/alerts"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        _Handler.seen = []
        patcher = mock.patch.object(c, "RETRY_BACKOFF_SECONDS", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def get(self, statuses):
        _Handler.statuses = list(statuses)
        with contextlib.redirect_stderr(io.StringIO()):
            return c.get_with_retry(self.url, {"Authorization": "Bearer tok"}, {"ref": "refs/pull/1/head", "page": "1"})

    def test_sends_query_and_auth_header(self):
        self.assertEqual(self.get([200]), (200, "[]"))
        path, auth = _Handler.seen[0]
        self.assertEqual(path, "/alerts?ref=refs%2Fpull%2F1%2Fhead&page=1")
        self.assertEqual(auth, "Bearer tok")

    def test_retries_transient_statuses(self):
        self.assertEqual(self.get([503, 429, 200])[0], 200)
        self.assertEqual(len(_Handler.seen), 3)

    def test_does_not_retry_client_errors(self):
        self.assertEqual(self.get([404])[0], 404)
        self.assertEqual(len(_Handler.seen), 1)

    def test_gives_up_after_max_attempts(self):
        with self.assertRaises(c.ApiRequestError):
            self.get([503] * c.MAX_ATTEMPTS)
        self.assertEqual(len(_Handler.seen), c.MAX_ATTEMPTS)

    def test_connection_errors_raise_api_error(self):
        with mock.patch.object(c.urllib.request, "urlopen", side_effect=OSError("refused")), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(c.ApiRequestError):
                c.get_with_retry(self.url, {}, {})


class MainTest(unittest.TestCase):
    def run_main(self, sarif_doc, env, alerts=None, fetch_error=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.sarif"
            path.write_text(json.dumps(sarif_doc), encoding="utf-8")
            fetch = mock.Mock(return_value=alerts or [], side_effect=fetch_error)
            with mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(sys, "argv", ["check_sarif_error.py", "--tool-name", "omni-audit", str(path)]), \
                    mock.patch.object(c, "fetch_open_alerts", fetch), \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return c.main(), fetch

    GH_ENV = {"GITHUB_REPOSITORY": "o/r", "GITHUB_TOKEN": "tok", "GITHUB_REF": "refs/pull/7/merge"}
    ERROR_SARIF = sarif([{"ruleId": "OA001", "level": "error", "message": {"text": "x"}}])

    def test_pr_merge_ref_is_read_as_head(self):
        _, fetch = self.run_main(sarif([]), self.GH_ENV)
        fetch.assert_called_once_with("o", "r", "tok", "refs/pull/7/head", "omni-audit")

    def test_alert_state_decides_exit_code(self):
        # GitHub alert state wins over the SARIF file, so dismissed alerts don't block.
        self.assertEqual(self.run_main(self.ERROR_SARIF, self.GH_ENV, alerts=[])[0], 0)
        self.assertEqual(self.run_main(sarif([]), self.GH_ENV, alerts=[alert()])[0], 1)

    def test_non_blocking_rules_are_ignored(self):
        rule = next(iter(c.NON_BLOCKING_RULES))
        self.assertEqual(self.run_main(sarif([]), self.GH_ENV, alerts=[alert(rule_id=rule)])[0], 0)

    def test_api_failure_exits_2(self):
        self.assertEqual(self.run_main(sarif([]), self.GH_ENV, fetch_error=c.ApiRequestError("boom"))[0], 2)

    def test_falls_back_to_sarif_without_token_or_code_scanning(self):
        no_token = {"GITHUB_REPOSITORY": "o/r", "GITHUB_REF": "refs/heads/main"}
        self.assertEqual(self.run_main(self.ERROR_SARIF, no_token)[0], 1)
        self.assertEqual(self.run_main(sarif([{"ruleId": "w", "level": "warning"}]), no_token)[0], 0)
        unavailable = c.CodeScanningUnavailable("Advanced Security must be enabled")
        self.assertEqual(self.run_main(self.ERROR_SARIF, self.GH_ENV, fetch_error=unavailable)[0], 1)


if __name__ == "__main__":
    unittest.main()
