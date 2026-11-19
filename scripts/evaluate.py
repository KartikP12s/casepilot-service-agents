"""Run exactly the published fixtures and report observed outcomes by category."""

import importlib.util
import json
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

spec = importlib.util.spec_from_file_location("cases", "tests/test_evaluation.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
summary = defaultdict(lambda: {"passed": 0, "failed": 0})
failures = []
for case in module.CASES:
    with tempfile.TemporaryDirectory() as directory:
        try:
            module.execute_case(case, Path(directory))
            summary[case["category"]]["passed"] += 1
        except Exception as error:
            summary[case["category"]]["failed"] += 1
            failures.append({"id": case["id"], "error": str(error)})
report = {
    "executed_at": datetime.now(timezone.utc).isoformat(),
    "total": len(module.CASES),
    "categories": dict(summary),
    "failures": failures,
}
Path("docs/evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
lines = [
    "# Synthetic evaluation",
    "",
    f"Executed: {report['executed_at']}",
    "",
    "| Category | Passed | Failed | Pass rate |",
    "|---|---:|---:|---:|",
]
for category, result in summary.items():
    rate = result["passed"] / (result["passed"] + result["failed"])
    lines.append(f"| {category} | {result['passed']} | {result['failed']} | {rate:.1%} |")
Path("docs/EVALUATION.md").write_text("\n".join(lines) + "\n")
print(json.dumps(report, indent=2))
raise SystemExit(bool(failures))
