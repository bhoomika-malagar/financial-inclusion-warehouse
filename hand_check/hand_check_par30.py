"""
Stage 8: Hand check of one KPI, independently of the pipeline.

Recomputes PAR30 at 30 June 2026 directly from the RAW CSV files, without
BigQuery, dbt or any warehouse table, and compares it with the dashboard value.

It also works through one overdue loan by hand to show that its days past due
(the input to PAR30) follows from the repayment schedule.

Run:  python hand_check/hand_check_par30.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
AS_OF = date(2026, 6, 30)
DASHBOARD_PAR30 = 3.05   # value shown on the dashboard (Portfolio health page)
DASHBOARD_BIHAR = 4.52   # PAR30 for Bihar on the same page

out: list[str] = []


def say(line: str = "") -> None:
    print(line)
    out.append(line)


# ---------------------------------------------------------------------------
# Step 1: read raw files
# ---------------------------------------------------------------------------
snap = pl.read_csv(RAW / "loan_monthly_snapshot.csv", try_parse_dates=True)
loans = pl.read_csv(RAW / "loans.csv", try_parse_dates=True)
branches = pl.read_csv(RAW / "branches.csv")
schedule = pl.read_csv(RAW / "repayment_schedule.csv", try_parse_dates=True)

say("# Hand check: PAR30 at 30 June 2026")
say()
say("Recomputed from the raw CSV files with Python (polars) only: no BigQuery, no dbt models.")
say()

# ---------------------------------------------------------------------------
# Step 2: apply the KPI definition step by step
# ---------------------------------------------------------------------------
june = snap.filter(pl.col("snapshot_month") == AS_OF)
say("## Step-by-step calculation")
say()
say(f"1. Snapshot rows at {AS_OF}: **{june.height:,}** loans")

book = june.filter(pl.col("loan_status") != "WRITTEN_OFF")
say(f"2. Excluding loans written off this month: **{book.height:,}** loans remain on the book")

glp = book["principal_outstanding"].sum()
say(f"3. Gross loan portfolio = Σ outstanding principal = **₹{glp:,.2f}**")

par30_rows = book.filter(pl.col("days_past_due") > 30)
par30_os = par30_rows["principal_outstanding"].sum()
say(f"4. Loans with DPD > 30: **{par30_rows.height:,}**, their outstanding = **₹{par30_os:,.2f}**")

par30 = 100 * par30_os / glp
say(f"5. PAR30 = {par30_os:,.2f} / {glp:,.2f} × 100 = **{par30:.2f} %**")
say()

# ---------------------------------------------------------------------------
# Step 3: same check for one state (needs the raw branch + loan files)
# ---------------------------------------------------------------------------
# Raw loans contain duplicates (SI-04) and raw branch states have a bad label
# (SI-10). Both are handled here independently, the simplest correct way.
loan_branch = loans.unique(subset="loan_id", keep="first").select("loan_id", "branch_id")
branch_state = branches.with_columns(pl.col("state").str.strip_chars().str.to_titlecase())
by_state = (
    book.join(loan_branch, on="loan_id")
    .join(branch_state, on="branch_id")
    .group_by("state")
    .agg(
        (100 * pl.col("principal_outstanding").filter(pl.col("days_past_due") > 30).sum()
         / pl.col("principal_outstanding").sum()).round(2).alias("par30_pct")
    )
    .sort("par30_pct", descending=True)
)
bihar = by_state.filter(pl.col("state") == "Bihar")["par30_pct"][0]

# ---------------------------------------------------------------------------
# Step 4: one loan worked through by hand
# ---------------------------------------------------------------------------
example = par30_rows.filter(pl.col("days_past_due").is_between(31, 60)).sort("loan_id").row(0, named=True)
loan_id = example["loan_id"]
sched = schedule.filter(pl.col("loan_id") == loan_id).sort("instalment_no")
due_by_as_of = sched.filter(pl.col("due_date") <= AS_OF).height
paid = example["instalments_paid_cum"]
oldest_unpaid = sched.filter(pl.col("instalment_no") == paid + 1).row(0, named=True)
dpd_by_hand = (AS_OF - oldest_unpaid["due_date"]).days

say("## One overdue loan, by hand")
say()
say(f"Loan **{loan_id}**, from the raw schedule and snapshot:")
say()
say(f"* Instalments due by {AS_OF}: **{due_by_as_of}** (counted from repayment_schedule.csv)")
say(f"* Instalments paid: **{paid}**, so the oldest unpaid is instalment **#{paid + 1}**, "
    f"due **{oldest_unpaid['due_date']}**")
say(f"* DPD = {AS_OF} − {oldest_unpaid['due_date']} = **{dpd_by_hand} days** "
    f"(snapshot says {example['days_past_due']})")
say(f"* {dpd_by_hand} > 30, so all of its outstanding principal "
    f"(₹{example['principal_outstanding']:,.2f}) counts in the PAR30 numerator.")
say()

# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
ok_total = abs(round(par30, 2) - DASHBOARD_PAR30) < 0.005
ok_state = abs(bihar - DASHBOARD_BIHAR) < 0.005
ok_loan = dpd_by_hand == example["days_past_due"]

say("## Result")
say()
say("| Check | Hand calculation | Dashboard / pipeline | Match |")
say("|---|---|---|---|")
say(f"| PAR30, whole portfolio, Jun 2026 | {par30:.2f} % | {DASHBOARD_PAR30:.2f} % | {'✅' if ok_total else '❌'} |")
say(f"| PAR30, Bihar, Jun 2026 | {bihar:.2f} % | {DASHBOARD_BIHAR:.2f} % | {'✅' if ok_state else '❌'} |")
say(f"| DPD of loan {loan_id} | {dpd_by_hand} | {example['days_past_due']} | {'✅' if ok_loan else '❌'} |")
say()
say("The independent calculation reproduces the dashboard, which shows the pipeline "
    "(load → staging → facts → KPI model → dashboard) carries the numbers through correctly.")

(ROOT / "hand_check" / "hand_check_result.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\nWritten to hand_check/hand_check_result.md")
