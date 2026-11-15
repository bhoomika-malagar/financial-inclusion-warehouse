"""
Synthetic data generator: Financial Inclusion Analytics Warehouse.

Produces invented "source system" files for a microfinance lender:

    data/raw/branches.csv              branch master (state -> branch)
    data/raw/products.csv              loan product master
    data/raw/borrowers.csv             borrower master (segment, branch)
    data/raw/loans.csv                 one row per loan (disbursement, amount, tenure)
    data/raw/repayment_schedule.csv    one row per instalment due (EMI schedule)
    data/raw/loan_monthly_snapshot.csv one row per loan per month-end (due, paid, DPD)
    data/raw/repayments.csv            one row per payment transaction (channel)

    data/ground_truth/seeded_issues_log.csv  what was broken on purpose (answer key)

How realism is built in
-----------------------
1. Every loan gets a hidden behaviour type: GOOD, LATE or DEFAULT.
   The probability depends on state x branch x product x segment, so repayment
   rates genuinely differ by branch and product.
2. GOOD payers pay within a few days of the due date. LATE payers pay most
   instalments 1-12 weeks late (sometimes in two parts). DEFAULT borrowers pay
   for a while and then stop completely.
3. The chance a payment is digital (UPI / bank transfer / NACH) rises over time,
   so the digital share of collections has a real trend.
4. After the clean data is built, known problems are injected (seeded) and every
   one is logged in data/ground_truth/ so tests can be checked against it.

Run:  python generator/generate_data.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl
import yaml

ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def month_end(d: np.ndarray) -> np.ndarray:
    """Last calendar day of the month for each datetime64[D] value."""
    return (d.astype("datetime64[M]") + np.timedelta64(1, "M")).astype("datetime64[D]") - np.timedelta64(1, "D")


def emi(principal: np.ndarray, annual_rate: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Equated monthly instalment for a reducing-balance loan."""
    r = annual_rate / 12
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


# ----------------------------------------------------------------------------
# 1. Dimensions: branches, products, borrowers
# ----------------------------------------------------------------------------
def build_branches(cfg: dict, rng: np.random.Generator) -> pl.DataFrame:
    rows = []
    i = 1
    for state, s in cfg["states"].items():
        for town in s["branches"]:
            rows.append(
                {
                    "branch_id": f"BR{i:03d}",
                    "branch_name": f"{town} Branch",
                    "state": state,
                    "opened_date": f"{rng.integers(2015, 2023)}-{rng.integers(1, 13):02d}-01",
                    # hidden fields used only inside the generator
                    "_state_risk": s["risk"],
                    "_state_digital": s["digital"],
                    "_branch_factor": float(rng.lognormal(0, cfg["branch_risk_sigma"])),
                }
            )
            i += 1
    return pl.DataFrame(rows)


def build_products(cfg: dict) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "product_id": pid,
                "product_name": p["name"],
                "product_category": p["category"],
                "annual_interest_rate": p["rate"],
                "min_amount": p["min"],
                "max_amount": p["max"],
            }
            for pid, p in cfg["products"].items()
        ]
    )


def build_borrowers(cfg: dict, branches: pl.DataFrame, n: int, rng) -> pl.DataFrame:
    seg_ids = list(cfg["segments"])
    seg_w = np.array([cfg["segments"][s]["weight"] for s in seg_ids])
    segment = rng.choice(seg_ids, size=n, p=seg_w / seg_w.sum())

    # Riskier states also have slightly more borrowers in rural branches: keep it simple
    branch_id = rng.choice(branches["branch_id"].to_numpy(), size=n)
    gender = np.where(segment == "S1", "F", rng.choice(["F", "M"], size=n, p=[0.45, 0.55]))
    age = np.clip(rng.normal(36, 9, n).round(), 19, 65).astype(int)

    return pl.DataFrame(
        {
            "borrower_id": [f"BW{i:06d}" for i in range(1, n + 1)],
            "branch_id": branch_id,
            "segment_id": segment,
            "segment_name": [cfg["segments"][s]["name"] for s in segment],
            "gender": gender,
            "age_at_onboarding": age,
        }
    )


# ----------------------------------------------------------------------------
# 2. Loans
# ----------------------------------------------------------------------------
def build_loans(cfg, branches, borrowers, rng) -> pl.DataFrame:
    n = cfg["n_loans"]
    n_borrowers = borrowers.height

    # Most loans go to a new borrower; the rest are repeat loans to existing borrowers
    borrower_idx = np.concatenate(
        [np.arange(n_borrowers), rng.integers(0, n_borrowers, n - n_borrowers)]
    )
    b = borrowers[borrower_idx]

    # Product depends on the borrower's segment
    product = np.empty(n, dtype=object)
    seg = b["segment_id"].to_numpy()
    for s_id, s in cfg["segments"].items():
        mask = seg == s_id
        pids, probs = zip(*s["products"].items())
        product[mask] = rng.choice(pids, size=mask.sum(), p=probs)

    # Disbursement dates: portfolio grows, so later months get more loans
    start = np.datetime64(str(cfg["disbursement_start"]), "M")
    end = np.datetime64(str(cfg["disbursement_end"]), "M")
    months = np.arange(start, end + np.timedelta64(1, "M"))
    w = 1 + cfg["portfolio_growth_per_month"] * np.arange(len(months))
    disb_month = rng.choice(months, size=n, p=w / w.sum())
    disb_day = rng.integers(1, 29, n)  # day 1-28 keeps every due date valid
    disb_date = disb_month.astype("datetime64[D]") + (disb_day - 1)

    # Amount and tenure from the product's range
    prod_cfg = cfg["products"]
    lo = np.array([prod_cfg[p]["min"] for p in product])
    hi = np.array([prod_cfg[p]["max"] for p in product])
    amount = lo + (hi - lo) * rng.beta(2, 3, n)  # skewed toward smaller loans
    amount = (np.round(amount / 1000) * 1000).astype(int)
    tenure = np.array([rng.choice(prod_cfg[p]["tenures"]) for p in product])
    rate = np.array([prod_cfg[p]["rate"] for p in product])

    loans = pl.DataFrame(
        {
            "loan_id": [f"LN{i:07d}" for i in range(1, n + 1)],
            "borrower_id": b["borrower_id"],
            "branch_id": b["branch_id"],
            "product_id": product.astype(str),
            "disbursement_date": disb_date,
            "principal_amount": amount,
            "annual_interest_rate": rate,
            "tenure_months": tenure,
        }
    ).sort("disbursement_date")
    loans = loans.with_columns(
        pl.format("LN{}", (pl.int_range(1, n + 1)).cast(pl.Utf8).str.zfill(7)).alias("loan_id")
    )

    loans = loans.with_columns(
        pl.Series(
            "emi_amount",
            np.round(
                emi(
                    loans["principal_amount"].to_numpy().astype(float),
                    loans["annual_interest_rate"].to_numpy(),
                    loans["tenure_months"].to_numpy(),
                )
            ),
        )
    )

    # ---- hidden behaviour type: GOOD / LATE / DEFAULT ----
    loans = loans.join(
        branches.select("branch_id", "_state_risk", "_branch_factor", "_state_digital"),
        on="branch_id",
    ).join(borrowers.select("borrower_id", "segment_id"), on="borrower_id")

    risk = (
        loans["_state_risk"].to_numpy()
        * loans["_branch_factor"].to_numpy()
        * np.array([prod_cfg[p]["risk"] for p in loans["product_id"]])
        * np.array([cfg["segments"][s]["risk"] for s in loans["segment_id"]])
    )
    beh = cfg["behaviour"]
    p_default = np.clip(beh["base_default_prob"] * risk, 0.005, 0.40)
    p_late = np.clip(beh["base_late_prob"] * np.sqrt(risk), 0.03, 0.45)
    u = rng.random(loans.height)
    btype = np.where(u < p_default, "DEFAULT", np.where(u < p_default + p_late, "LATE", "GOOD"))

    # Defaulters stop paying at some instalment (more often early than late)
    ten = loans["tenure_months"].to_numpy()
    default_at = 2 + np.floor((ten - 2) * rng.beta(1.3, 2.5, loans.height)).astype(int)

    loans = loans.with_columns(
        pl.Series("_behaviour", btype),
        pl.Series("_default_at", default_at),
        # source-system audit column; used later for de-duplication
        (pl.col("disbursement_date").cast(pl.Datetime) + pl.duration(hours=18)).alias("last_updated_at"),
    ).sort("loan_id")
    return loans


# ----------------------------------------------------------------------------
# 3. Repayment schedule + actual payment dates
# ----------------------------------------------------------------------------
def build_schedule(loans: pl.DataFrame, as_of: np.datetime64, rng) -> pl.DataFrame:
    ten = loans["tenure_months"].to_numpy()
    idx = np.repeat(np.arange(loans.height), ten)
    # instalment number 1..tenure within each loan
    k = np.arange(len(idx)) - np.repeat(np.cumsum(ten) - ten, ten) + 1

    disb = loans["disbursement_date"].to_numpy().astype("datetime64[D]")[idx]
    day = (disb - disb.astype("datetime64[M]").astype("datetime64[D]")).astype(int)
    due = (disb.astype("datetime64[M]") + k).astype("datetime64[D]") + day

    # Amortisation split: interest on outstanding balance, rest is principal
    P = loans["principal_amount"].to_numpy().astype(float)[idx]
    r = loans["annual_interest_rate"].to_numpy()[idx] / 12
    E = loans["emi_amount"].to_numpy()[idx]
    bal_before = P * (1 + r) ** (k - 1) - E * ((1 + r) ** (k - 1) - 1) / r
    bal_after = np.maximum(P * (1 + r) ** k - E * ((1 + r) ** k - 1) / r, 0)
    principal_comp = np.round(bal_before - bal_after, 2)
    interest_comp = np.round(E - principal_comp, 2)

    # Payment delay (days) by behaviour type
    btype = loans["_behaviour"].to_numpy()[idx]
    default_at = loans["_default_at"].to_numpy()[idx]
    n = len(idx)
    delay = np.where(
        btype == "GOOD",
        rng.integers(-5, 6, n),  # a few days early or late
        np.where(
            btype == "LATE",
            rng.exponential(10, n) + 2 + (rng.random(n) < 0.10) * rng.integers(25, 75, n),
            rng.exponential(8, n),  # defaulters before they stop
        ),
    ).round().astype(int)

    paid = due + delay
    never_paid = (btype == "DEFAULT") & (k >= default_at)
    not_yet = paid > as_of
    paid = paid.astype("datetime64[D]")
    paid_mask = ~(never_paid | not_yet)

    # Payments are applied to the OLDEST unpaid instalment first (FIFO), as a
    # loan-management system does. So within each loan, the earliest payment
    # date settles instalment 1, the next settles instalment 2, and so on.
    # (Each instalment can be at most 5 days early, as before.)
    paid_int = np.where(paid_mask, paid.astype("int64"), np.iinfo("int64").max)
    order = np.lexsort((paid_int, idx))          # by loan, then payment date
    paid_int = paid_int[order]
    paid_mask = paid_int != np.iinfo("int64").max
    paid = np.where(paid_mask, paid_int, 0).astype("datetime64[D]")

    sched = pl.DataFrame(
        {
            "loan_id": loans["loan_id"].to_numpy()[idx],
            "instalment_no": k,
            "due_date": due,
            "amount_due": E,
            "principal_component": principal_comp,
            "interest_component": interest_comp,
            "_paid_date": np.where(paid_mask, paid, np.datetime64("NaT", "D")),
            "_behaviour": btype,
        }
    )
    return sched


# ----------------------------------------------------------------------------
# 4. Payment transactions with channels
# ----------------------------------------------------------------------------
def build_transactions(cfg, loans, sched, rng) -> pl.DataFrame:
    paid = sched.filter(pl.col("_paid_date").is_not_null())

    # Late payers sometimes split one instalment into two payments
    split = (paid["_behaviour"] == "LATE").to_numpy() & (
        rng.random(paid.height) < cfg["behaviour"]["split_payment_prob"]
    )
    full = paid.filter(~pl.Series(split)).select(
        "loan_id", pl.col("_paid_date").alias("txn_date"), pl.col("amount_due").alias("amount")
    )
    s = paid.filter(pl.Series(split))
    frac = rng.uniform(0.3, 0.7, s.height)
    first_amt = np.round(s["amount_due"].to_numpy() * frac)
    part1 = pl.DataFrame(
        {
            "loan_id": s["loan_id"],
            "txn_date": s["_paid_date"].to_numpy() - rng.integers(3, 15, s.height).astype("timedelta64[D]"),
            "amount": first_amt,
        }
    )
    part2 = pl.DataFrame(
        {"loan_id": s["loan_id"], "txn_date": s["_paid_date"], "amount": s["amount_due"].to_numpy() - first_amt}
    )
    txns = pl.concat([full, part1, part2.with_columns(pl.col("txn_date").cast(pl.Date))], how="vertical_relaxed")

    # ---- channel: digital probability rises over time ----
    txns = txns.join(loans.select("loan_id", "product_id", "_state_digital"), on="loan_id")
    dg = cfg["digital"]
    t0 = np.datetime64(str(cfg["disbursement_start"]), "D")
    years = (txns["txn_date"].to_numpy().astype("datetime64[D]") - t0).astype(int) / 365.25
    is_msme = (txns["product_id"] == "P02").to_numpy()
    p_digital = np.clip(
        txns["_state_digital"].to_numpy() + dg["growth_per_year"] * years + dg["msme_bonus"] * is_msme,
        0.05,
        dg["max_share"],
    )
    digital = rng.random(txns.height) < p_digital

    channel = np.full(txns.height, "CASH", dtype=object)
    for mix_name, mask in [("mix_msme", is_msme), ("mix_default", ~is_msme)]:
        m = digital & mask
        ch, p = zip(*dg[mix_name].items())
        channel[m] = rng.choice(ch, size=m.sum(), p=p)

    source = np.select(
        [channel == "CASH", channel == "UPI"],
        ["branch_collection_app", "upi_gateway"],
        default="bank_feed",
    )

    txns = (
        txns.with_columns(pl.Series("channel", channel.astype(str)), pl.Series("source_system", source))
        .select("loan_id", "txn_date", "amount", "channel", "source_system")
        .sort("txn_date", "loan_id")
        .with_columns(pl.format("TX{}", pl.int_range(1, pl.len() + 1).cast(pl.Utf8).str.zfill(8)).alias("txn_id"))
        .select("txn_id", "loan_id", "txn_date", "amount", "channel", "source_system")
    )
    return txns


# ----------------------------------------------------------------------------
# 5. Monthly loan snapshot (what the loan-management system reports each month-end)
# ----------------------------------------------------------------------------
def build_snapshots(loans, sched, txns, as_of: np.datetime64, write_off_dpd: int) -> pl.DataFrame:
    # Loan closes when its last instalment is paid
    closure = sched.group_by("loan_id").agg(
        pl.col("_paid_date").max().alias("closed_on"),
        pl.col("_paid_date").null_count().alias("unpaid"),
    ).with_columns(pl.when(pl.col("unpaid") == 0).then(pl.col("closed_on")).alias("closed_on"))
    base = loans.select("loan_id", "disbursement_date", "principal_amount").join(
        closure.select("loan_id", "closed_on"), on="loan_id"
    )

    paid_in_month = txns.group_by(
        "loan_id", pl.col("txn_date").dt.month_end().alias("snapshot_month")
    ).agg(pl.col("amount").sum().alias("amount_paid_in_month"))

    first = np.datetime64(loans["disbursement_date"].min(), "D")
    month_ends = month_end(np.arange(first.astype("datetime64[M]"), as_of.astype("datetime64[M]") + np.timedelta64(1, "M")).astype("datetime64[D]"))

    frames = []
    for m in month_ends:
        m_start = m.astype("datetime64[M]").astype("datetime64[D]")
        active = base.filter(
            (pl.col("disbursement_date") <= m)
            & (pl.col("closed_on").is_null() | (pl.col("closed_on") >= m_start))
        ).select("loan_id", "principal_amount")
        if active.height == 0:
            continue
        s = sched.join(active.select("loan_id"), on="loan_id")
        agg = s.group_by("loan_id").agg(
            (pl.col("due_date") <= m).sum().alias("instalments_due_cum"),
            ((pl.col("_paid_date") <= m) & (pl.col("due_date") <= m)).sum().alias("instalments_paid_cum"),  # counted against dues only
            pl.col("amount_due").filter(pl.col("due_date").dt.month_end() == m).sum().alias("amount_due_in_month"),
            pl.col("principal_component").filter(pl.col("_paid_date") <= m).sum().alias("principal_repaid"),
            pl.col("due_date")
            .filter((pl.col("due_date") <= m) & (pl.col("_paid_date").is_null() | (pl.col("_paid_date") > m)))
            .min()
            .alias("oldest_overdue"),
        )
        frames.append(
            active.join(agg, on="loan_id").with_columns(
                pl.lit(m).alias("snapshot_month"),
                (pl.col("principal_amount") - pl.col("principal_repaid")).clip(lower_bound=0).round(2).alias("principal_outstanding"),
                pl.when(pl.col("oldest_overdue").is_null())
                .then(0)
                .otherwise((pl.lit(m) - pl.col("oldest_overdue")).dt.total_days())
                .alias("days_past_due"),
            )
        )

    snap = (
        pl.concat(frames)
        .join(paid_in_month, on=["loan_id", "snapshot_month"], how="left")
        .with_columns(pl.col("amount_paid_in_month").fill_null(0))
        .join(base.select("loan_id", "closed_on"), on="loan_id")
        .sort("loan_id", "snapshot_month")
    )

    # Write-off: the first month a loan crosses the DPD threshold it is written off,
    # and it no longer appears in later snapshots (it leaves the active book).
    snap = snap.with_columns(
        pl.when(pl.col("days_past_due") > write_off_dpd).then(pl.col("snapshot_month")).min().over("loan_id").alias("_wo_month")
    ).filter(pl.col("_wo_month").is_null() | (pl.col("snapshot_month") <= pl.col("_wo_month")))

    snap = snap.with_columns(
        pl.when(pl.col("snapshot_month") == pl.col("_wo_month"))
        .then(pl.lit("WRITTEN_OFF"))
        .when(pl.col("closed_on").is_not_null() & (pl.col("closed_on").dt.month_end() == pl.col("snapshot_month")))
        .then(pl.lit("CLOSED"))
        .otherwise(pl.lit("ACTIVE"))
        .alias("loan_status")
    ).select(
        "loan_id",
        "snapshot_month",
        "loan_status",
        "instalments_due_cum",
        "instalments_paid_cum",
        "amount_due_in_month",
        "amount_paid_in_month",
        "principal_outstanding",
        "days_past_due",
    ).sort("snapshot_month", "loan_id")
    return snap


# ----------------------------------------------------------------------------
# 6. Seed known data problems (and log every one of them)
# ----------------------------------------------------------------------------
def seed_issues(cfg, branches, loans, txns, snap, rng):
    si = cfg["seeded_issues"]
    log = []

    def record(issue_id, table, column, n, keys):
        log.append(
            {
                "issue_id": issue_id,
                "table": table,
                "column": column,
                "rows_affected": int(n),
                "example_keys": ", ".join(map(str, list(keys)[:5])),
            }
        )

    # SI-02: a whole month of collections missing for one branch (file never arrived)
    mm = si["missing_month"]
    branch_loans = loans.filter(pl.col("branch_id") == mm["branch_id"])["loan_id"]
    y, mo = map(int, str(mm["month"]).split("-"))
    drop = txns["loan_id"].is_in(branch_loans.implode()) & (txns["txn_date"].dt.year() == y) & (txns["txn_date"].dt.month() == mo)
    record("SI-02", "repayments", "txn_date", drop.sum(), [f"{mm['branch_id']} {mm['month']}"])
    txns = txns.filter(~drop)

    # SI-03: one source switched to paise after an API change
    pu = si["paise_unit"]
    paise = (txns["source_system"] == pu["source_system"]) & (txns["txn_date"] >= pu["from_date"])
    record("SI-03", "repayments", "amount", paise.sum(), txns.filter(paise)["txn_id"].head(5))
    txns = txns.with_columns(pl.when(paise).then(pl.col("amount") * 100).otherwise(pl.col("amount")).alias("amount"))

    # SI-05: sign flipped on some amounts
    i = rng.choice(txns.height, si["negative_amounts"], replace=False)
    mask = np.zeros(txns.height, bool); mask[i] = True
    record("SI-05", "repayments", "amount", mask.sum(), txns.filter(pl.Series(mask))["txn_id"])
    txns = txns.with_columns(pl.when(pl.Series(mask)).then(-pl.col("amount")).otherwise(pl.col("amount")).alias("amount"))

    # SI-07: payment dated before the loan was disbursed
    i = rng.choice(txns.height, si["payment_before_disbursement"], replace=False)
    mask = np.zeros(txns.height, bool); mask[i] = True
    disb = txns.select("loan_id").join(loans.select("loan_id", "disbursement_date"), on="loan_id", how="left")["disbursement_date"].to_numpy()
    shift = rng.integers(5, 60, txns.height).astype("timedelta64[D]")
    new_dates = np.where(mask, disb - shift, txns["txn_date"].to_numpy())
    txns = txns.with_columns(pl.Series("txn_date", new_dates).cast(pl.Date))
    record("SI-07", "repayments", "txn_date", mask.sum(), txns.filter(pl.Series(mask))["txn_id"])

    # SI-11: future-dated transactions (after the as-of date)
    i = rng.choice(txns.height, si["future_dated_txns"], replace=False)
    mask = np.zeros(txns.height, bool); mask[i] = True
    as_of = np.datetime64(str(cfg["as_of_date"]), "D")
    new_dates = np.where(mask, as_of + shift, txns["txn_date"].to_numpy())
    txns = txns.with_columns(pl.Series("txn_date", new_dates).cast(pl.Date))
    record("SI-11", "repayments", "txn_date", mask.sum(), txns.filter(pl.Series(mask))["txn_id"])

    # SI-08: channel missing
    i = rng.choice(txns.height, si["missing_channel"], replace=False)
    mask = np.zeros(txns.height, bool); mask[i] = True
    txns = txns.with_columns(pl.when(pl.Series(mask)).then(None).otherwise(pl.col("channel")).alias("channel"))
    record("SI-08", "repayments", "channel", mask.sum(), txns.filter(pl.Series(mask))["txn_id"])

    # SI-06: payments pointing at loan IDs that do not exist
    orphans = txns.sample(si["orphan_loan_ids"], seed=int(rng.integers(1e9))).with_columns(
        pl.format("LN9{}", pl.int_range(1, pl.len() + 1).cast(pl.Utf8).str.zfill(6)).alias("loan_id"),
        pl.format("TX9{}", pl.int_range(1, pl.len() + 1).cast(pl.Utf8).str.zfill(7)).alias("txn_id"),
    )
    record("SI-06", "repayments", "loan_id", orphans.height, orphans["txn_id"])
    txns = pl.concat([txns, orphans])

    # SI-01: exact duplicate rows (file re-sent / double-loaded)
    dups = txns.sample(si["duplicate_txn_rows"], seed=int(rng.integers(1e9)))
    record("SI-01", "repayments", "(all)", dups.height, dups["txn_id"])
    txns = pl.concat([txns, dups]).sample(fraction=1.0, shuffle=True, seed=int(rng.integers(1e9)))

    # SI-04: duplicate loan IDs (record re-sent with a later timestamp)
    dl = loans.sample(si["duplicate_loan_ids"], seed=int(rng.integers(1e9))).with_columns(
        (pl.col("last_updated_at") + pl.duration(days=3)).alias("last_updated_at")
    )
    record("SI-04", "loans", "loan_id", dl.height, dl["loan_id"])
    loans = pl.concat([loans, dl]).sort("loan_id")

    # SI-09: snapshot says more instalments paid than were due
    i = rng.choice(np.flatnonzero(snap["instalments_due_cum"].to_numpy() > 0), si["paid_exceeds_due"], replace=False)
    mask = np.zeros(snap.height, bool); mask[i] = True
    snap = snap.with_columns(
        pl.when(pl.Series(mask)).then(pl.col("instalments_due_cum") + 1).otherwise(pl.col("instalments_paid_cum")).alias("instalments_paid_cum")
    )
    record("SI-09", "loan_monthly_snapshot", "instalments_paid_cum", mask.sum(), snap.filter(pl.Series(mask))["loan_id"])

    # SI-10: inconsistent state label on one branch
    bs = si["bad_state_label"]
    branches = branches.with_columns(
        pl.when(pl.col("branch_id") == bs["branch_id"]).then(pl.lit(bs["value"])).otherwise(pl.col("state")).alias("state")
    )
    record("SI-10", "branches", "state", 1, [bs["branch_id"]])

    log_df = pl.DataFrame(log).sort("issue_id")
    return branches, loans, txns, snap, log_df


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=ROOT / "generator" / "config.yaml")
    ap.add_argument("--out", default=ROOT / "data")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    rng = np.random.default_rng(cfg["seed"])
    as_of = np.datetime64(str(cfg["as_of_date"]), "D")
    raw_dir = Path(args.out) / "raw"
    truth_dir = Path(args.out) / "ground_truth"
    raw_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)

    print("1/6 dimensions ...")
    branches = build_branches(cfg, rng)
    products = build_products(cfg)
    n_borrowers = int(cfg["n_loans"] * (1 - cfg["repeat_borrower_share"]))
    borrowers = build_borrowers(cfg, branches, n_borrowers, rng)

    print("2/6 loans ...")
    loans = build_loans(cfg, branches, borrowers, rng)

    print("3/6 repayment schedule ...")
    sched = build_schedule(loans, as_of, rng)

    print("4/6 transactions ...")
    txns = build_transactions(cfg, loans, sched, rng)

    print("5/6 monthly snapshots ...")
    snap = build_snapshots(loans, sched, txns, as_of, cfg["behaviour"]["write_off_dpd"])

    print("6/6 seeding data problems ...")
    loans_out = loans.select(
        "loan_id", "borrower_id", "branch_id", "product_id", "disbursement_date",
        "principal_amount", "annual_interest_rate", "tenure_months", "emi_amount", "last_updated_at",
    )
    branches_out = branches.select("branch_id", "branch_name", "state", "opened_date")
    branches_out, loans_out, txns_out, snap_out, log = seed_issues(cfg, branches_out, loans_out, txns, snap, rng)

    # ---- write files ----
    outputs = {
        "branches": branches_out,
        "products": products,
        "borrowers": borrowers,
        "loans": loans_out,
        "repayment_schedule": sched.drop("_paid_date", "_behaviour"),
        "loan_monthly_snapshot": snap_out,
        "repayments": txns_out,
    }
    for name, df in outputs.items():
        df.write_csv(raw_dir / f"{name}.csv")
    log.write_csv(truth_dir / "seeded_issues_log.csv")

    # ---- quick sanity summary ----
    print("\nRows written:")
    for name, df in outputs.items():
        print(f"  {name:<24}{df.height:>12,}")
    beh = loans.group_by("_behaviour").len().sort("_behaviour")
    print("\nHidden behaviour mix:", dict(zip(beh["_behaviour"], beh["len"])))
    print("\nSeeded issues:")
    print(log.select("issue_id", "table", "rows_affected"))


if __name__ == "__main__":
    main()
