# Raw Data Profiling Report

Generated 2026-11-16 02:35 from BigQuery dataset `fin-inclusion-dwh.raw` (as-of date 2026-06-30).

Profiling runs **before** any modelling, on the raw tables exactly as loaded. Its goal is to list every data problem that later cleaning and tests must handle.

## Summary

| Check | What it looks at | Anomalies | Finding |
|---|---|---|---|
| P-01 | Row counts and key uniqueness | ⚠️ 1,225 | loans: 25 duplicate keys, repayments: 1,200 duplicate keys |
| P-02 | Exact duplicate rows | ⚠️ 1,200 | repayments: 1,200 exact duplicate rows. loans: 0 exact duplicates (so loan key duplicates differ in some column, e.g. last_updated_at, which means they are re-sent records, not double-loads). |
| P-03 | Null values per column | ⚠️ 251 | repayments.channel: 251 nulls |
| P-04 | Categorical value hygiene | ⚠️ 1 | Suspicious labels: branches.state = [karnataka ] |
| P-05 | Repayment amount distribution | ⚠️ 40 | 40 negative amounts; max payment 2,709,600 vs median 3,692 (suspiciously large values exist). |
| P-06 | Average payment size by source system and month | ⚠️ 10 | 10 source-months with average payment more than 10x away from normal, all in: upi_gateway (from 2025-10-01). |
| P-07 | Orphan foreign keys | ⚠️ 61 | repayments.loan_id -> loans: 61 |
| P-08 | Date sanity | ⚠️ 42 | 30 payments dated before disbursement; 12 payments dated after 2026-06-30. |
| P-09 | Branch-month completeness | ⚠️ 1 | Branch-months with no collections: BR012 2025-08 |
| P-10 | Loan snapshot consistency | ⚠️ 15 | 15 rows with instalments paid > due; 0 negative DPD; 0 negative outstanding. |
| P-11 | Reconciliation: snapshot vs transactions | ⚠️ 16 | 16 months where the transaction file and the loan snapshot disagree by more than 1%. |

## Profiling findings vs seeded issues

| Seeded issue | Description | Rows seeded | Found by profiling? | Check(s) |
|---|---|---|---|---|
| SI-01 | Duplicate transaction rows | 1200 | ✅ Yes | P-01, P-02 |
| SI-02 | Missing month for one branch | 945 | ✅ Yes | P-09 |
| SI-03 | Amounts in different units from one source | 142881 | ✅ Yes | P-06 |
| SI-04 | Duplicate loan IDs | 25 | ✅ Yes | P-01 |
| SI-05 | Negative amounts | 40 | ✅ Yes | P-05 |
| SI-06 | Orphan loan IDs | 60 | ✅ Yes | P-07 |
| SI-07 | Payment before disbursement | 30 | ✅ Yes | P-08 |
| SI-08 | Missing payment channel | 250 | ✅ Yes | P-03 |
| SI-09 | Instalments paid exceed instalments due | 15 | ✅ Yes | P-10 |
| SI-10 | Inconsistent state label | 1 | ✅ Yes | P-04 |
| SI-11 | Future-dated transactions | 12 | ✅ Yes | P-08 |

## Details

### P-01: Row counts and key uniqueness

_Why:_ A primary key must identify exactly one row.

| table_name | row_count | distinct_keys | duplicate_keys |
|---|---|---|---|
| loans | 55,025 | 55,000 | 25 |
| loan_monthly_snapshot | 682,740 | 682,740 | 0 |
| borrowers | 49,500 | 49,500 | 0 |
| repayments | 636,001 | 634,801 | 1,200 |
| repayment_schedule | 1,045,332 | 1,045,332 | 0 |
| products | 4 | 4 | 0 |
| branches | 30 | 30 | 0 |

**Finding:** loans: 25 duplicate keys, repayments: 1,200 duplicate keys

### P-02: Exact duplicate rows

_Why:_ Separates true double-loads (identical rows) from re-sent records (same key, different values).

| table_name | exact_duplicate_rows |
|---|---|
| loans | 0 |
| repayments | 1,200 |

**Finding:** repayments: 1,200 exact duplicate rows. loans: 0 exact duplicates (so loan key duplicates differ in some column, e.g. last_updated_at, which means they are re-sent records, not double-loads).

### P-03: Null values per column

_Why:_ Required fields (IDs, dates, amounts, channel) should never be empty.

| table_name | column_name | null_count |
|---|---|---|
| repayments | channel | 251 |

**Finding:** repayments.channel: 251 nulls

### P-04: Categorical value hygiene

_Why:_ Labels should come from a fixed list, with consistent case and no stray spaces.

| column_name | value | n | suspicious |
|---|---|---|---|
| branches.state | [Bihar] | 5 | 0 |
| branches.state | [Karnataka] | 4 | 0 |
| branches.state | [Maharashtra] | 5 | 0 |
| branches.state | [Odisha] | 5 | 0 |
| branches.state | [Tamil Nadu] | 5 | 0 |
| branches.state | [Uttar Pradesh] | 5 | 0 |
| branches.state | [karnataka ] | 1 | 1 |
| loan_monthly_snapshot.loan_status | [ACTIVE] | 664,164 | 0 |
| loan_monthly_snapshot.loan_status | [CLOSED] | 16,722 | 0 |
| loan_monthly_snapshot.loan_status | [WRITTEN_OFF] | 1,854 | 0 |
| repayments.channel | [BANK_TRANSFER] | 77,992 | 0 |
| repayments.channel | [CASH] | 245,507 | 0 |
| repayments.channel | [NACH] | 60,458 | 0 |
| repayments.channel | [NULL] | 251 | 0 |
| repayments.channel | [UPI] | 251,793 | 0 |
| repayments.source_system | [bank_feed] | 138,507 | 0 |
| repayments.source_system | [branch_collection_app] | 245,593 | 0 |
| repayments.source_system | [upi_gateway] | 251,901 | 0 |

**Finding:** Suspicious labels: branches.state = [karnataka ]

### P-05: Repayment amount distribution

_Why:_ Payments should be positive and of a plausible size (close to an EMI).

| min_amount | p50 | p99 | max_amount | negative | zero |
|---|---|---|---|---|---|
| -335,200.00 | 3,692.00 | 806,200.00 | 2,709,600.00 | 40 | 0 |

**Finding:** 40 negative amounts; max payment 2,709,600 vs median 3,692 (suspiciously large values exist).

### P-06: Average payment size by source system and month

_Why:_ A sudden ~100x jump for one source suggests a unit change (rupees vs paise).

| source_system | month | avg_amount | source_median | ratio | n |
|---|---|---|---|---|---|
| upi_gateway | 2025-10-01 | 350,370.00 | 3,787.00 | 92.50 | 13,000 |
| upi_gateway | 2025-11-01 | 351,040.00 | 3,787.00 | 92.70 | 13,533 |
| upi_gateway | 2025-12-01 | 350,877.00 | 3,787.00 | 92.70 | 14,720 |
| upi_gateway | 2026-01-01 | 350,983.00 | 3,787.00 | 92.70 | 15,207 |
| upi_gateway | 2026-02-01 | 347,450.00 | 3,787.00 | 91.80 | 15,388 |
| upi_gateway | 2026-03-01 | 343,421.00 | 3,787.00 | 90.70 | 17,434 |
| upi_gateway | 2026-04-01 | 345,726.00 | 3,787.00 | 91.30 | 17,110 |
| upi_gateway | 2026-05-01 | 344,492.00 | 3,787.00 | 91.00 | 18,318 |
| upi_gateway | 2026-06-01 | 345,888.00 | 3,787.00 | 91.30 | 18,455 |
| upi_gateway | 2026-08-01 | 79,595.00 | 3,787.00 | 21.00 | 4 |

**Finding:** 10 source-months with average payment more than 10x away from normal, all in: upi_gateway (from 2025-10-01).

### P-07: Orphan foreign keys

_Why:_ Every repayment must belong to a known loan; every loan to a known branch, product and borrower.

| relationship | orphan_rows |
|---|---|
| repayments.loan_id -> loans | 61 |
| loans.branch_id -> branches | 0 |
| loans.product_id -> products | 0 |
| loans.borrower_id -> borrowers | 0 |
| snapshot.loan_id -> loans | 0 |

**Finding:** repayments.loan_id -> loans: 61

### P-08: Date sanity

_Why:_ Payments must fall between the loan's disbursement date and the as-of date (2026-06-30).

| first_txn | last_txn | before_disbursement | after_as_of |
|---|---|---|---|
| 2023-11-23 | 2026-08-25 | 30 | 12 |

**Finding:** 30 payments dated before disbursement; 12 payments dated after 2026-06-30.

### P-09: Branch-month completeness

_Why:_ An active branch with zero collections in a month usually means a file never arrived.

| branch_id | missing_month |
|---|---|
| BR012 | 2025-08-01 |

**Finding:** Branch-months with no collections: BR012 2025-08

### P-10: Loan snapshot consistency

_Why:_ Instalments paid can never exceed instalments due; DPD and outstanding can never be negative.

| paid_gt_due | negative_dpd | negative_outstanding |
|---|---|---|
| 15 | 0 | 0 |

**Finding:** 15 rows with instalments paid > due; 0 negative DPD; 0 negative outstanding.

### P-11: Reconciliation: snapshot vs transactions

_Why:_ Two systems report the same money; monthly totals should agree within 1%.

| month | snapshot_paid | txn_paid | diff_pct |
|---|---|---|---|
| 2023-11-01 | None | 2,837.00 | None |
| 2024-02-01 | 4,844,326.00 | 5,413,577.00 | 11.75 |
| 2024-06-01 | 27,799,667.00 | 28,579,300.00 | 2.80 |
| 2024-10-01 | 54,391,971.00 | 55,150,555.00 | 1.39 |
| 2025-08-01 | 107,942,967.00 | 104,532,952.00 | -3.16 |
| 2025-10-01 | 116,506,585.00 | 4,625,836,352.00 | 3,870.45 |
| 2025-11-01 | 117,524,630.00 | 4,820,689,643.00 | 4,001.85 |
| 2025-12-01 | 125,105,041.00 | 5,238,607,626.00 | 4,087.37 |
| 2026-01-01 | 127,149,755.00 | 5,411,138,263.00 | 4,155.72 |
| 2026-02-01 | 124,235,652.00 | 5,416,623,528.00 | 4,259.96 |
| 2026-03-01 | 139,749,066.00 | 6,067,116,681.00 | 4,241.44 |
| 2026-04-01 | 134,791,144.00 | 5,991,263,952.00 | 4,344.85 |
| 2026-05-01 | 141,873,238.00 | 6,389,300,262.00 | 4,403.53 |
| 2026-06-01 | 139,980,970.00 | 6,459,716,190.00 | 4,514.71 |
| 2026-07-01 | None | 12,112.00 | None |
| 2026-08-01 | None | 324,579.00 | None |

**Finding:** 16 months where the transaction file and the loan snapshot disagree by more than 1%.
