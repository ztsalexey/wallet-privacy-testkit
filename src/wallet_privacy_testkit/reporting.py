"""Recompute a complete lab run and render bounded human and CI reports."""

from contextlib import contextmanager
import hashlib
from importlib.resources import files
import json
from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from . import __version__
from .privacy import analyze_privacy
from .recovery import verify_recovery_report
from .study import analyze_study


SCOPE = (
    "Checks consistency of supplied observations, not their authenticity. "
    "Privacy metrics describe local send-command windows in a small, correlated sample; "
    "they are not a privacy guarantee, wallet ranking, or identity linkage. "
    "No detector accuracy threshold is used to pass this verification."
)
EXAMPLE_FILES = (
    "report.json", "privacy-manifest.json", "calibration.trace.jsonl",
    "evaluation.trace.jsonl",
)


@contextmanager
def example_run():
    """Materialize exact retained evidence, including from a zipped installation."""
    resource = files("wallet_privacy_testkit").joinpath("example")
    provenance = json.loads(resource.joinpath("provenance.json").read_text(encoding="utf-8"))
    if set(provenance["sha256"]) != set(EXAMPLE_FILES):
        raise ValueError("packaged example has an invalid file inventory")
    with tempfile.TemporaryDirectory(prefix="wpt-example-") as directory:
        root = Path(directory)
        for name in EXAMPLE_FILES:
            data = resource.joinpath(name).read_bytes()
            if hashlib.sha256(data).hexdigest() != provenance["sha256"][name]:
                raise ValueError(f"packaged example checksum mismatch: {name}")
            (root / name).write_bytes(data)
        yield root


def verify_run(directory, *, example=False):
    """Require recovery plus exactly one privacy experiment; never trust saved verdicts."""
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"run directory does not exist or is not a directory: {root}")
    checks = []

    def check(name, operation):
        try:
            detail = operation()
        except (OSError, ValueError) as error:
            checks.append({"name": name, "status": "fail", "error": str(error)})
        else:
            checks.append({"name": name, "status": "pass", "detail": detail})

    check("recovery", lambda: verify_recovery_report(
        json.loads((root / "report.json").read_text(encoding="utf-8"))))

    def privacy():
        manifests = [root / name for name in ("privacy-manifest.json", "study-manifest.json")
                     if (root / name).exists()]
        if len(manifests) != 1:
            raise ValueError("expected exactly one privacy-manifest.json or study-manifest.json")
        manifest = manifests[0]
        study = manifest.name == "study-manifest.json"
        result = (analyze_study if study else analyze_privacy)(manifest)
        # Keep session and group rates, but leave thousands of individual windows
        # to analyze-privacy/analyze-study. They use the same independent analysis.
        sessions = [{k: v for k, v in session.items() if k not in ("observations", "payment_timing")}
                    for session in result["sessions"]]
        return {"kind": "study" if study else "continuous", "manifest": manifest.name,
                "threshold_bytes": result["threshold_bytes"], "window_ns": result["window_ns"],
                "sessions": sessions, "groups": result.get("groups", []),
                "payment_operations": sum(s["payment_operations"] for s in sessions),
                "scope": result["scope"]}

    check("privacy_evidence", privacy)
    return {"schema_version": 1, "testkit_version": __version__,
            "source": "packaged retained example" if example else str(root),
            "example": example,
            "status": "pass" if all(c["status"] == "pass" for c in checks) else "fail",
            "checks": checks, "scope": SCOPE}


def _metrics_line(label, metrics):
    return (f"  {label}: TP={metrics['tp']} FP={metrics['fp']} "
            f"FN={metrics['fn']} TN={metrics['tn']}; "
            f"recall={metrics['recall']:.1%}, false-positive rate={metrics['false_positive_rate']:.1%}")


def render_text(report):
    lines = [f"Wallet Privacy Testkit {report['testkit_version']}", f"Source: {report['source']}"]
    if report["example"]:
        lines.append("Retained real regtest evidence; this command runs no wallets or network tests.")
    lines.append(f"Verification: {report['status'].upper()}")
    for check in report["checks"]:
        if check["status"] == "fail":
            lines.append(f"FAIL {check['name']}: {check['error']}")
            continue
        detail = check["detail"]
        if check["name"] == "recovery":
            lines.append(f"PASS recovery: {len(detail['scenarios'])} scenarios; live no-mining control detected")
            lines.extend(f"  {s['name']}: confirmed; recipient delta {s['recipient_balance_delta']} zatoshi"
                         for s in detail["scenarios"])
        else:
            lines.append(f"PASS privacy evidence consistency: {len(detail['sessions'])} sessions, "
                         f"{detail['payment_operations']} payment operations")
            lines.append(f"  Detector: largest client TLS record >= {detail['threshold_bytes']} bytes; "
                         f"{detail['window_ns'] / 1e9:g}-second windows")
            lines.append("  Held-out evaluation (TP/FP/FN/TN count windows, not payments):")
            rows = detail["groups"] or detail["sessions"]
            for row in rows:
                if row["split"] == "evaluation":
                    label = f"{row['wallet']} / {row['condition']}" if "wallet" in row else "evaluation"
                    lines.append(_metrics_line(label, row["metrics"]))
    lines.extend(["", report["scope"]])
    return "\n".join(lines) + "\n"


def _xml_text(value):
    # Evidence errors may contain control characters; XML 1.0 forbids them.
    return "".join(c if c in "\t\n\r" or 0x20 <= ord(c) <= 0xD7FF
                   or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF
                   else "\ufffd" for c in str(value))


def render_junit(report):
    suite = ET.Element("testsuite", name="wallet-privacy-testkit", tests=str(len(report["checks"])),
                       failures=str(sum(c["status"] == "fail" for c in report["checks"])), errors="0")
    properties = ET.SubElement(suite, "properties")
    for key in ("source", "testkit_version", "scope"):
        ET.SubElement(properties, "property", name=key, value=_xml_text(report[key]))
    for check in report["checks"]:
        case = ET.SubElement(suite, "testcase", classname="wallet_privacy_testkit", name=check["name"])
        if check["status"] == "fail":
            ET.SubElement(case, "failure", message=_xml_text(check["error"])).text = _xml_text(check["error"])
        else:
            ET.SubElement(case, "system-out").text = _xml_text(json.dumps(check["detail"], indent=2))
    ET.SubElement(suite, "system-out").text = _xml_text(render_text(report))
    ET.indent(suite)
    return ET.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def render_report(report, format="text"):
    if format == "text":
        return render_text(report)
    if format == "junit":
        return render_junit(report)
    if format == "json":
        return json.dumps(report, indent=2) + "\n"
    raise ValueError(f"unsupported report format: {format}")
