import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from wallet_privacy_testkit.reporting import example_run, render_report, verify_run


class ReportingTests(unittest.TestCase):
    def cli(self, *arguments):
        return subprocess.run([sys.executable, "-m", "wallet_privacy_testkit.cli", *arguments],
                              text=True, capture_output=True, timeout=60)

    def test_packaged_example_recomputes_real_failures_and_misses(self):
        with example_run() as root:
            result = verify_run(root, example=True)
        self.assertEqual(result["status"], "pass")
        recovery, privacy = result["checks"]
        self.assertEqual(len(recovery["detail"]["scenarios"]), 5)
        self.assertIn("node_confirmation", recovery["detail"]["negative_control_detected"])
        held_out = privacy["detail"]["sessions"][1]
        self.assertEqual([held_out["metrics"][k] for k in ("tp", "fp", "fn", "tn")], [3, 1, 3, 11])
        self.assertNotIn("observations", held_out)
        text = render_report(result)
        self.assertIn("runs no wallets", text)
        self.assertIn("count windows, not payments", text)
        self.assertIn("not a privacy guarantee", text)
        junit = ET.fromstring(render_report(result, "junit"))
        self.assertEqual(junit.attrib["failures"], "0")
        self.assertEqual([c.attrib["name"] for c in junit.findall("testcase")],
                         ["recovery", "privacy_evidence"])

    def test_inconsistent_recovery_still_reports_privacy_and_fails_ci(self):
        with example_run() as root:
            path = root / "report.json"
            data = json.loads(path.read_text())
            data["status"] = "pass"
            data["scenarios"][0]["recipient"]["after"] += 1
            path.write_text(json.dumps(data))
            process = self.cli("verify-run", str(root), "--format", "junit")
        self.assertEqual(process.returncode, 1, process.stderr)
        junit = ET.fromstring(process.stdout)
        self.assertEqual(junit.attrib["failures"], "1")
        self.assertIn("recipient_balance_delta", junit.find("testcase/failure").attrib["message"])
        self.assertIsNotNone(junit.findall("testcase")[1].find("system-out"))

    def test_missing_ambiguous_and_corrupt_privacy_evidence_fail(self):
        for mode in ("missing", "ambiguous", "checksum", "malformed"):
            with self.subTest(mode=mode), example_run() as root:
                path = root / "privacy-manifest.json"
                if mode == "missing":
                    path.unlink()
                elif mode == "ambiguous":
                    (root / "study-manifest.json").write_text("{}")
                elif mode == "checksum":
                    (root / "evaluation.trace.jsonl").write_text("{}\n")
                else:
                    path.write_text("null")
                result = verify_run(root)
                self.assertEqual(result["status"], "fail")
                self.assertEqual(result["checks"][0]["status"], "pass")
                self.assertEqual(result["checks"][1]["status"], "fail")

    def test_empty_directory_is_not_a_success(self):
        with tempfile.TemporaryDirectory() as directory:
            process = self.cli("verify-run", directory, "--format", "json")
        self.assertEqual(process.returncode, 1)
        result = json.loads(process.stdout)
        self.assertTrue(all(c["status"] == "fail" for c in result["checks"]))

    def test_cli_usage_errors_and_exclusive_output(self):
        for arguments in (("verify-run",), ("verify-run", ".", "--example"),
                          ("verify-run", "/no-such-wpt-directory"),
                          ("verify-recovery", "/no-such-wpt-report")):
            process = self.cli(*arguments)
            self.assertEqual(process.returncode, 2)
            self.assertIn("wpt: error:", process.stderr)
            self.assertNotIn("Traceback", process.stderr)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "ci.xml"
            process = self.cli("verify-run", "--example", "--format", "junit", "--output", str(output))
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout, "")
            original = output.read_bytes()
            process = self.cli("verify-run", "--example", "--output", str(output))
            self.assertEqual(process.returncode, 2)
            self.assertEqual(output.read_bytes(), original)

    def test_junit_errors_escape_xml_and_disallowed_controls(self):
        with tempfile.TemporaryDirectory() as directory:
            result = verify_run(directory)
        result["checks"][0]["error"] = '<failure attr="x"> & \x00\ud800'
        junit = ET.fromstring(render_report(result, "junit"))
        self.assertEqual(junit.attrib["failures"], "2")
        self.assertIn('<failure attr="x"> &', junit.find("testcase/failure").text)

    def test_bundled_evidence_matches_retained_source(self):
        root = Path(__file__).resolve().parents[1]
        source = root / "evidence/zingolib-v5-continuous/orbstack-aarch64"
        if not source.is_dir():
            self.skipTest("source evidence unavailable outside source archive")
        with example_run() as example:
            for path in example.iterdir():
                self.assertEqual(hashlib.sha256(path.read_bytes()).digest(),
                                 hashlib.sha256((source / path.name).read_bytes()).digest())

    def test_randomized_study_uses_frozen_detector_and_preserves_groups(self):
        root = Path(__file__).resolve().parents[1] / "evidence/randomized-study"
        if not root.is_dir():
            self.skipTest("full study unavailable outside source archive")
        result = verify_run(root)
        self.assertEqual(result["status"], "pass")
        detail = result["checks"][1]["detail"]
        self.assertEqual(len(detail["sessions"]), 21)
        self.assertEqual(detail["payment_operations"], 63)
        self.assertEqual(detail["threshold_bytes"], 9207)
        self.assertEqual(len(detail["groups"]), 7)
        self.assertIn("zcash-devtool / bandwidth: TP=0 FP=0 FN=16 TN=56", render_report(result))
