"""
Stage 5: Turn dbt test results into a readable report.

Reads dbt_project/target/run_results.json (written by `dbt test`) and
dbt_project/target/manifest.json, and writes docs/test_results.md with:
  * every test, its layer, status and number of failing rows
  * which seeded issues the tests caught (via meta.seeded_issue on each test)

Run after `dbt test`:  python scripts/test_report.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "dbt_project" / "target"

manifest = json.loads((TARGET / "manifest.json").read_text(encoding="utf-8"))
results = json.loads((TARGET / "run_results.json").read_text(encoding="utf-8"))["results"]
seeded = yaml.safe_load((ROOT / "generator" / "seeded_issues.yaml").read_text(encoding="utf-8"))


def layer_of(node: dict) -> str:
    """Where the test runs: on raw sources, staging, or marts."""
    deps = node.get("depends_on", {}).get("nodes", [])
    if any(d.startswith("source.") for d in deps) and not any(d.startswith("model.") for d in deps):
        return "Raw source"
    models = [d.split(".")[-1] for d in deps if d.startswith("model.")]
    if any(m.startswith(("fct_", "dim_", "audit_")) for m in models):
        return "Mart"
    if models:
        return "Staging"
    return "Raw source"


rows = []
for r in results:
    node = manifest["nodes"].get(r["unique_id"])
    if not node or node["resource_type"] != "test":
        continue
    meta = node.get("config", {}).get("meta", {}) or node.get("meta", {})
    rows.append(
        {
            "name": node["name"],
            "kind": "Generic" if node.get("test_metadata") else "Custom SQL",
            "layer": layer_of(node),
            "severity": node["config"].get("severity", "ERROR").upper(),
            "status": r["status"].upper(),
            "failures": r.get("failures") or 0,
            "issue": meta.get("seeded_issue", ""),
        }
    )

order = {"Raw source": 0, "Staging": 1, "Mart": 2}
rows.sort(key=lambda x: (order[x["layer"]], x["status"] == "PASS", x["name"]))
counts = Counter(r["status"] for r in rows)

icon = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "❌ FAIL", "ERROR": "❌ ERROR"}
lines = [
    "# Data Quality Test Results",
    "",
    f"Generated {datetime.now():%Y-%m-%d %H:%M} from `dbt test`.",
    "",
    f"**{len(rows)} tests:** " + ", ".join(f"{k} = {v}" for k, v in sorted(counts.items())),
    "",
    "Tests run at three layers:",
    "",
    "* **Raw source** (severity warn): detect problems in what the source systems send.",
    "* **Staging** (severity error): prove each cleaning step worked.",
    "* **Mart** (severity error, two business checks warn): guarantee what the dashboard reads.",
    "",
    "## Seeded issues: caught or missed",
    "",
    "| Issue | Description | Caught? | Test(s) that caught it | Failing rows |",
    "|---|---|---|---|---|",
]
for s in seeded:
    hits = [r for r in rows if r["issue"] == s["id"] and r["status"] in ("WARN", "FAIL", "ERROR") and r["failures"]]
    caught = "✅ Caught" if hits else "❌ Missed"
    names = "<br>".join(f"`{h['name']}`" for h in hits) or "-"
    fails = "<br>".join(f"{h['failures']:,}" for h in hits) or "-"
    lines.append(f"| {s['id']} | {s['name']} | {caught} | {names} | {fails} |")

lines += ["", "## All tests", "", "| Layer | Test | Type | Severity | Status | Failing rows | Seeded issue |", "|---|---|---|---|---|---|---|"]
for r in rows:
    lines.append(
        f"| {r['layer']} | `{r['name']}` | {r['kind']} | {r['severity']} | {icon.get(r['status'], r['status'])} | {r['failures']:,} | {r['issue']} |"
    )

out = ROOT / "docs" / "test_results.md"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Report written to {out}")
print("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
