"""
Stage 2b: Profile the raw BigQuery tables BEFORE modelling.

Runs a set of generic data-quality checks (keys, duplicates, nulls, value
ranges, date sanity, completeness, reconciliation) against dataset `raw` and
writes the findings to profiling/profiling_report.md.

At the end the report compares what profiling found against the seeded-issue
answer key (data/ground_truth/seeded_issues_log.csv).

Run:  python profiling/profile_raw.py
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
PROJECT = os.environ.get("GCP_PROJECT", "fin-inclusion-dwh")
LOCATION = "asia-south1"
CFG = yaml.safe_load((ROOT / "generator" / "config.yaml").read_text())
AS_OF = str(CFG["as_of_date"])
START = str(CFG["disbursement_start"])

client = bigquery.Client(project=PROJECT, location=LOCATION)


def t(name: str) -> str:
    """Fully-qualified raw table name."""
    return f"`{PROJECT}.raw.{name}`"


def run(sql: str) -> tuple[list[str], list[tuple]]:
    res = client.query(sql).result()
    cols = [f.name for f in res.schema]
    return cols, [tuple(r.values()) for r in res]


def md_table(cols, rows, limit: int = 15) -> str:
    if not rows:
        return "_No rows._\n"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows[:limit]:
        out.append("| " + " | ".join(f"{v:,.2f}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v) for v in r) + " |")
    if len(rows) > limit:
        out.append(f"\n_… {len(rows) - limit} more rows not shown._")
    return "\n".join(out) + "\n"


@dataclass
class Check:
    id: str
    title: str
    why: str
    targets: list[str] = field(default_factory=list)  # seeded issue IDs this check can reveal
    anomalies: int = 0
    finding: str = ""
    detail_md: str = ""
    found: list[str] = field(default_factory=list)   # seeded issue IDs actually revealed


checks: list[Check] = []


# ---------------------------------------------------------------------------
# P-01  Row counts and primary-key uniqueness
# ---------------------------------------------------------------------------
c = Check("P-01", "Row counts and key uniqueness", "A primary key must identify exactly one row.", ["SI-01", "SI-04"])
keys = {
    "branches": "branch_id", "products": "product_id", "borrowers": "borrower_id", "loans": "loan_id",
    "repayment_schedule": "CONCAT(loan_id, '-', CAST(instalment_no AS STRING))",
    "loan_monthly_snapshot": "CONCAT(loan_id, '-', CAST(snapshot_month AS STRING))",
    "repayments": "txn_id",
}
sql = " UNION ALL ".join(
    f"SELECT '{tbl}' AS table_name, COUNT(*) AS row_count, COUNT(DISTINCT {k}) AS distinct_keys, "
    f"COUNT(*) - COUNT(DISTINCT {k}) AS duplicate_keys FROM {t(tbl)}"
    for tbl, k in keys.items()
)
cols, rows = run(sql)
c.detail_md = md_table(cols, rows)
dup = {r[0]: r[3] for r in rows}
c.anomalies = sum(dup.values())
c.finding = ", ".join(f"{k}: {v:,} duplicate keys" for k, v in dup.items() if v) or "All keys unique."
if dup.get("repayments"): c.found.append("SI-01")
if dup.get("loans"): c.found.append("SI-04")
checks.append(c)

# ---------------------------------------------------------------------------
# P-02  Exact duplicate rows (every column identical)
# ---------------------------------------------------------------------------
c = Check("P-02", "Exact duplicate rows", "Separates true double-loads (identical rows) from re-sent records (same key, different values).", ["SI-01", "SI-04"])
cols, rows = run(
    f"SELECT 'repayments' AS table_name, COUNT(*) - COUNT(DISTINCT TO_JSON_STRING(r)) AS exact_duplicate_rows FROM {t('repayments')} r "
    f"UNION ALL SELECT 'loans', COUNT(*) - COUNT(DISTINCT TO_JSON_STRING(l)) FROM {t('loans')} l"
)
c.detail_md = md_table(cols, rows)
ex = dict(rows)
c.anomalies = sum(ex.values())
c.finding = (
    f"repayments: {ex['repayments']:,} exact duplicate rows. loans: {ex['loans']:,} exact duplicates "
    f"(so loan key duplicates differ in some column, e.g. last_updated_at, which means they are re-sent records, not double-loads)."
)
if ex["repayments"]: c.found.append("SI-01")
checks.append(c)

# ---------------------------------------------------------------------------
# P-03  Null counts in every column (built from INFORMATION_SCHEMA)
# ---------------------------------------------------------------------------
c = Check("P-03", "Null values per column", "Required fields (IDs, dates, amounts, channel) should never be empty.", ["SI-08"])
_, colrows = run(f"SELECT table_name, column_name FROM `{PROJECT}.raw.INFORMATION_SCHEMA.COLUMNS` ORDER BY table_name, ordinal_position")
by_table: dict[str, list[str]] = {}
for tbl, col in colrows:
    by_table.setdefault(tbl, []).append(col)
null_rows = []
for tbl, cs in by_table.items():
    sel = ", ".join(f"COUNTIF({col} IS NULL) AS {col}" for col in cs)
    cc, rr = run(f"SELECT {sel} FROM {t(tbl)}")
    for col, n in zip(cc, rr[0]):
        if n:
            null_rows.append((tbl, col, n))
c.detail_md = md_table(["table_name", "column_name", "null_count"], null_rows)
c.anomalies = sum(r[2] for r in null_rows)
c.finding = "; ".join(f"{a}.{b}: {n:,} nulls" for a, b, n in null_rows) or "No nulls."
if any(r[0] == "repayments" and r[1] == "channel" for r in null_rows): c.found.append("SI-08")
checks.append(c)

# ---------------------------------------------------------------------------
# P-04  Categorical values (spelling, case, whitespace)
# ---------------------------------------------------------------------------
c = Check("P-04", "Categorical value hygiene", "Labels should come from a fixed list, with consistent case and no stray spaces.", ["SI-10"])
cols, rows = run(
    f"""
    SELECT 'branches.state' AS column_name, CONCAT('[', state, ']') AS value, COUNT(*) AS n,
           LOGICAL_OR(state != TRIM(state) OR state != INITCAP(state)) AS suspicious
    FROM {t('branches')} GROUP BY state
    UNION ALL SELECT 'repayments.channel', CONCAT('[', IFNULL(channel, 'NULL'), ']'), COUNT(*), FALSE FROM {t('repayments')} GROUP BY channel
    UNION ALL SELECT 'repayments.source_system', CONCAT('[', source_system, ']'), COUNT(*), FALSE FROM {t('repayments')} GROUP BY source_system
    UNION ALL SELECT 'loan_monthly_snapshot.loan_status', CONCAT('[', loan_status, ']'), COUNT(*), FALSE FROM {t('loan_monthly_snapshot')} GROUP BY loan_status
    ORDER BY column_name, value
    """
)
c.detail_md = md_table(cols, rows, limit=40)
bad = [r for r in rows if r[3]]
c.anomalies = len(bad)
c.finding = ("Suspicious labels: " + ", ".join(f"{r[0]} = {r[1]}" for r in bad)) if bad else "All labels clean."
if bad: c.found.append("SI-10")
checks.append(c)

# ---------------------------------------------------------------------------
# P-05  Amount ranges
# ---------------------------------------------------------------------------
c = Check("P-05", "Repayment amount distribution", "Payments should be positive and of a plausible size (close to an EMI).", ["SI-05", "SI-03"])
cols, rows = run(
    f"""
    SELECT MIN(amount) AS min_amount, APPROX_QUANTILES(amount, 100)[OFFSET(50)] AS p50,
           APPROX_QUANTILES(amount, 100)[OFFSET(99)] AS p99, MAX(amount) AS max_amount,
           COUNTIF(amount < 0) AS negative, COUNTIF(amount = 0) AS zero
    FROM {t('repayments')}
    """
)
c.detail_md = md_table(cols, rows)
neg = rows[0][4]
c.anomalies = neg
c.finding = f"{neg:,} negative amounts; max payment {rows[0][3]:,.0f} vs median {rows[0][1]:,.0f} (suspiciously large values exist)."
if neg: c.found.append("SI-05")
checks.append(c)

# ---------------------------------------------------------------------------
# P-06  Average payment size by source and month (unit consistency)
# ---------------------------------------------------------------------------
c = Check("P-06", "Average payment size by source system and month", "A sudden ~100x jump for one source suggests a unit change (rupees vs paise).", ["SI-03"])
cols, rows = run(
    f"""
    WITH m AS (
      SELECT source_system, DATE_TRUNC(txn_date, MONTH) AS month, AVG(amount) AS avg_amount, COUNT(*) AS n
      FROM {t('repayments')} WHERE amount > 0 GROUP BY 1, 2
    ), med AS (
      SELECT source_system, APPROX_QUANTILES(avg_amount, 2)[OFFSET(1)] AS median_monthly_avg FROM m GROUP BY 1
    )
    SELECT m.source_system, m.month, ROUND(m.avg_amount, 0) AS avg_amount,
           ROUND(med.median_monthly_avg, 0) AS source_median, ROUND(m.avg_amount / med.median_monthly_avg, 1) AS ratio, m.n
    FROM m JOIN med USING (source_system)
    WHERE m.avg_amount > 10 * med.median_monthly_avg OR m.avg_amount < 0.1 * med.median_monthly_avg
    ORDER BY m.source_system, m.month
    """
)
c.detail_md = md_table(cols, rows, limit=20)
c.anomalies = len(rows)
if rows:
    srcs = sorted({r[0] for r in rows})
    c.finding = f"{len(rows)} source-months with average payment more than 10x away from normal, all in: {', '.join(srcs)} (from {min(r[1] for r in rows)})."
    c.found.append("SI-03")
else:
    c.finding = "Payment sizes consistent across sources."
checks.append(c)

# ---------------------------------------------------------------------------
# P-07  Referential integrity
# ---------------------------------------------------------------------------
c = Check("P-07", "Orphan foreign keys", "Every repayment must belong to a known loan; every loan to a known branch, product and borrower.", ["SI-06"])
cols, rows = run(
    f"""
    SELECT 'repayments.loan_id -> loans' AS relationship, COUNT(*) AS orphan_rows
    FROM {t('repayments')} r LEFT JOIN (SELECT DISTINCT loan_id FROM {t('loans')}) l USING (loan_id) WHERE l.loan_id IS NULL
    UNION ALL SELECT 'loans.branch_id -> branches', COUNT(*) FROM {t('loans')} l LEFT JOIN {t('branches')} b USING (branch_id) WHERE b.branch_id IS NULL
    UNION ALL SELECT 'loans.product_id -> products', COUNT(*) FROM {t('loans')} l LEFT JOIN {t('products')} p USING (product_id) WHERE p.product_id IS NULL
    UNION ALL SELECT 'loans.borrower_id -> borrowers', COUNT(*) FROM {t('loans')} l LEFT JOIN {t('borrowers')} b USING (borrower_id) WHERE b.borrower_id IS NULL
    UNION ALL SELECT 'snapshot.loan_id -> loans', COUNT(*) FROM {t('loan_monthly_snapshot')} s LEFT JOIN (SELECT DISTINCT loan_id FROM {t('loans')}) l USING (loan_id) WHERE l.loan_id IS NULL
    """
)
c.detail_md = md_table(cols, rows)
c.anomalies = sum(r[1] for r in rows)
c.finding = "; ".join(f"{r[0]}: {r[1]:,}" for r in rows if r[1]) or "No orphans."
if rows[0][1]: c.found.append("SI-06")
checks.append(c)

# ---------------------------------------------------------------------------
# P-08  Date sanity
# ---------------------------------------------------------------------------
c = Check("P-08", "Date sanity", f"Payments must fall between the loan's disbursement date and the as-of date ({AS_OF}).", ["SI-07", "SI-11"])
cols, rows = run(
    f"""
    SELECT MIN(r.txn_date) AS first_txn, MAX(r.txn_date) AS last_txn,
           COUNTIF(r.txn_date < l.disbursement_date) AS before_disbursement,
           COUNTIF(r.txn_date > DATE '{AS_OF}') AS after_as_of
    FROM {t('repayments')} r
    LEFT JOIN (SELECT loan_id, MIN(disbursement_date) AS disbursement_date FROM {t('loans')} GROUP BY 1) l USING (loan_id)
    """
)
c.detail_md = md_table(cols, rows)
before, after = rows[0][2], rows[0][3]
c.anomalies = before + after
c.finding = f"{before:,} payments dated before disbursement; {after:,} payments dated after {AS_OF}."
if before: c.found.append("SI-07")
if after: c.found.append("SI-11")
checks.append(c)

# ---------------------------------------------------------------------------
# P-09  Completeness: every branch should have collections every month
# ---------------------------------------------------------------------------
c = Check("P-09", "Branch-month completeness", "An active branch with zero collections in a month usually means a file never arrived.", ["SI-02"])
cols, rows = run(
    f"""
    WITH bm AS (
      SELECT l.branch_id, DATE_TRUNC(r.txn_date, MONTH) AS month, COUNT(*) AS n
      FROM {t('repayments')} r JOIN (SELECT DISTINCT loan_id, branch_id FROM {t('loans')}) l USING (loan_id)
      WHERE r.txn_date BETWEEN DATE '{START}' AND DATE '{AS_OF}'
      GROUP BY 1, 2
    ), span AS (SELECT branch_id, MIN(month) AS first_m, MAX(month) AS last_m FROM bm GROUP BY 1),
    cal AS (SELECT branch_id, month FROM span, UNNEST(GENERATE_DATE_ARRAY(first_m, last_m, INTERVAL 1 MONTH)) AS month)
    SELECT cal.branch_id, cal.month AS missing_month
    FROM cal LEFT JOIN bm USING (branch_id, month) WHERE bm.n IS NULL ORDER BY 1, 2
    """
)
c.detail_md = md_table(cols, rows)
c.anomalies = len(rows)
c.finding = ("Branch-months with no collections: " + ", ".join(f"{r[0]} {r[1]:%Y-%m}" for r in rows)) if rows else "Every branch has collections every month."
if rows: c.found.append("SI-02")
checks.append(c)

# ---------------------------------------------------------------------------
# P-10  Snapshot internal consistency
# ---------------------------------------------------------------------------
c = Check("P-10", "Loan snapshot consistency", "Instalments paid can never exceed instalments due; DPD and outstanding can never be negative.", ["SI-09"])
cols, rows = run(
    f"""
    SELECT COUNTIF(instalments_paid_cum > instalments_due_cum) AS paid_gt_due,
           COUNTIF(days_past_due < 0) AS negative_dpd,
           COUNTIF(principal_outstanding < 0) AS negative_outstanding
    FROM {t('loan_monthly_snapshot')}
    """
)
c.detail_md = md_table(cols, rows)
c.anomalies = sum(rows[0])
c.finding = f"{rows[0][0]:,} rows with instalments paid > due; {rows[0][1]:,} negative DPD; {rows[0][2]:,} negative outstanding."
if rows[0][0]: c.found.append("SI-09")
checks.append(c)

# ---------------------------------------------------------------------------
# P-11  Reconciliation: snapshot collections vs transaction file, by month
# ---------------------------------------------------------------------------
c = Check("P-11", "Reconciliation: snapshot vs transactions", "Two systems report the same money; monthly totals should agree within 1%.", ["SI-02", "SI-03"])
cols, rows = run(
    f"""
    WITH s AS (SELECT DATE_TRUNC(snapshot_month, MONTH) AS month, SUM(amount_paid_in_month) AS snapshot_paid FROM {t('loan_monthly_snapshot')} GROUP BY 1),
         r AS (SELECT DATE_TRUNC(txn_date, MONTH) AS month, SUM(amount) AS txn_paid FROM {t('repayments')} GROUP BY 1)
    SELECT month, ROUND(snapshot_paid, 0) AS snapshot_paid, ROUND(txn_paid, 0) AS txn_paid,
           ROUND(100 * (txn_paid - snapshot_paid) / NULLIF(snapshot_paid, 0), 2) AS diff_pct
    FROM s FULL JOIN r USING (month)
    WHERE ABS(IFNULL(txn_paid, 0) - IFNULL(snapshot_paid, 0)) > 0.01 * GREATEST(IFNULL(snapshot_paid, 0), 1)
    ORDER BY month
    """
)
c.detail_md = md_table(cols, rows, limit=40)
c.anomalies = len(rows)
c.finding = f"{len(rows)} months where the transaction file and the loan snapshot disagree by more than 1%." if rows else "Monthly totals reconcile."
checks.append(c)


# ---------------------------------------------------------------------------
# Write the report
# ---------------------------------------------------------------------------
truth_path = ROOT / "data" / "ground_truth" / "seeded_issues_log.csv"
seeded = yaml.safe_load((ROOT / "generator" / "seeded_issues.yaml").read_text())
truth = {r["issue_id"]: r for r in csv.DictReader(open(truth_path))} if truth_path.exists() else {}

lines = [
    "# Raw Data Profiling Report",
    "",
    f"Generated {datetime.now():%Y-%m-%d %H:%M} from BigQuery dataset `{PROJECT}.raw` (as-of date {AS_OF}).",
    "",
    "Profiling runs **before** any modelling, on the raw tables exactly as loaded. "
    "Its goal is to list every data problem that later cleaning and tests must handle.",
    "",
    "## Summary",
    "",
    "| Check | What it looks at | Anomalies | Finding |",
    "|---|---|---|---|",
]
for ch in checks:
    flag = "⚠️ " if ch.anomalies else "✅ "
    lines.append(f"| {ch.id} | {ch.title} | {flag}{ch.anomalies:,} | {ch.finding} |")

lines += ["", "## Profiling findings vs seeded issues", "",
          "| Seeded issue | Description | Rows seeded | Found by profiling? | Check(s) |", "|---|---|---|---|---|"]
for s in seeded:
    found_by = [ch.id for ch in checks if s["id"] in ch.found]
    rows_seeded = truth.get(s["id"], {}).get("rows_affected", "?")
    lines.append(f"| {s['id']} | {s['name']} | {rows_seeded} | {'✅ Yes' if found_by else '❌ No'} | {', '.join(found_by) or '-'} |")

lines += ["", "## Details", ""]
for ch in checks:
    lines += [f"### {ch.id}: {ch.title}", "", f"_Why:_ {ch.why}", "", ch.detail_md, f"**Finding:** {ch.finding}", ""]

out = ROOT / "profiling" / "profiling_report.md"
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Report written to {out}")
for ch in checks:
    print(f"  {ch.id} {ch.title:<45} anomalies: {ch.anomalies:,}")
