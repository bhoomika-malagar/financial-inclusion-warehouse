# Raw Data Profiling Report

Generated 2026-11-15 21:09 from BigQuery dataset `fin-inclusion-dwh.raw` (as-of date 2026-06-30).

Profiling runs **before** any modelling, on the raw tables exactly as loaded. Its goal is to list every data problem that later cleaning and tests must handle.

## Summary

| Check | What it looks at | Anomalies | Finding |
|---|---|---|---|
| P-01 | Row counts and key uniqueness | ⚠️ 1,225 | repayments: 1,200 duplicate keys, loans: 25 duplicate keys |
| P-02 | Exact duplicate rows | ⚠️ 1,200 | repayments: 1,200 exact duplicate rows. loans: 0 exact duplicates (so loan key duplicates differ in some column, e.g. last_updated_at, which means they are re-sent records, not double-loads). |
| P-03 | Null values per column | ⚠️ 250 | repayments.channel: 250 nulls |
| P-04 | Categorical value hygiene | ⚠️ 1 | Suspicious labels: branches.state = [karnataka ] |
| P-05 | Repayment amount distribution | ⚠️ 40 | 40 negative amounts; max payment 2,663,100 vs median 3,692 (suspiciously large values exist). |
| P-06 | Average payment size by source system and month | ⚠️ 11 | 11 source-months with average payment more than 10x away from normal, all in: upi_gateway (from 2025-10-01). |
| P-07 | Orphan foreign keys | ⚠️ 60 | repayments.loan_id -> loans: 60 |
| P-08 | Date sanity | ⚠️ 42 | 30 payments dated before disbursement; 12 payments dated after 2026-06-30. |
| P-09 | Branch-month completeness | ⚠️ 1 | Branch-months with no collections: BR012 2025-08 |
| P-10 | Loan snapshot consistency | ⚠️ 15 | 15 rows with instalments paid > due; 0 negative DPD; 0 negative outstanding. |
| P-11 | Reconciliation: snapshot vs transactions | ⚠️ 14 | 14 months where the transaction file and the loan snapshot disagree by more than 1%. |

## Profiling findings vs seeded issues

| Seeded issue | Description | Rows seeded | Found by profiling? | Check(s) |
|---|---|---|---|---|
| SI-01 | Duplicate transaction rows | 1200 | ✅ Yes | P-01, P-02 |
| SI-02 | Missing month for one branch | 945 | ✅ Yes | P-09 |
| SI-03 | Amounts in different units from one source | 143003 | ✅ Yes | P-06 |
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
| branches | 30 | 30 | 0 |
| products | 4 | 4 | 0 |
| loan_monthly_snapshot | 682,740 | 682,740 | 0 |
| repayments | 636,001 | 634,801 | 1,200 |
| borrowers | 49,500 | 49,500 | 0 |
| loans | 55,025 | 55,000 | 25 |
| repayment_schedule | 1,045,332 | 1,045,332 | 0 |

**Finding:** repayments: 1,200 duplicate keys, loans: 25 duplicate keys

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
| repayments | channel | 250 |

**Finding:** repayments.channel: 250 nulls

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
| repayments.channel | [BANK_TRANSFER] | 77,963 | 0 |
| repayments.channel | [CASH] | 245,548 | 0 |
| repayments.channel | [NACH] | 60,478 | 0 |
| repayments.channel | [NULL] | 250 | 0 |
| repayments.channel | [UPI] | 251,762 | 0 |
| repayments.source_system | [bank_feed] | 138,489 | 0 |
| repayments.source_system | [branch_collection_app] | 245,644 | 0 |
| repayments.source_system | [upi_gateway] | 251,868 | 0 |

**Finding:** Suspicious labels: branches.state = [karnataka ]

### P-05: Repayment amount distribution

_Why:_ Payments should be positive and of a plausible size (close to an EMI).

| min_amount | p50 | p99 | max_amount | negative | zero |
|---|---|---|---|---|---|
| -498,700.00 | 3,692.00 | 812,400.00 | 2,663,100.00 | 40 | 0 |

**Finding:** 40 negative amounts; max payment 2,663,100 vs median 3,692 (suspiciously large values exist).

### P-06: Average payment size by source system and month

_Why:_ A sudden ~100x jump for one source suggests a unit change (rupees vs paise).

| source_system | month | avg_amount | source_median | ratio | n |
|---|---|---|---|---|---|
| upi_gateway | 2025-10-01 | 349,733.00 | 3,795.00 | 92.10 | 13,000 |
| upi_gateway | 2025-11-01 | 350,247.00 | 3,795.00 | 92.30 | 13,613 |
| upi_gateway | 2025-12-01 | 350,066.00 | 3,795.00 | 92.20 | 14,685 |
| upi_gateway | 2026-01-01 | 346,769.00 | 3,795.00 | 91.40 | 15,161 |
| upi_gateway | 2026-02-01 | 347,217.00 | 3,795.00 | 91.50 | 15,319 |
| upi_gateway | 2026-03-01 | 347,074.00 | 3,795.00 | 91.40 | 17,477 |
| upi_gateway | 2026-04-01 | 347,322.00 | 3,795.00 | 91.50 | 17,253 |
| upi_gateway | 2026-05-01 | 348,423.00 | 3,795.00 | 91.80 | 18,336 |
| upi_gateway | 2026-06-01 | 345,346.00 | 3,795.00 | 91.00 | 18,421 |
| upi_gateway | 2026-07-01 | 121,062.00 | 3,795.00 | 31.90 | 3 |
| upi_gateway | 2026-08-01 | 221,550.00 | 3,795.00 | 58.40 | 2 |

**Finding:** 11 source-months with average payment more than 10x away from normal, all in: upi_gateway (from 2025-10-01).

### P-07: Orphan foreign keys

_Why:_ Every repayment must belong to a known loan; every loan to a known branch, product and borrower.

| relationship | orphan_rows |
|---|---|
| repayments.loan_id -> loans | 60 |
| loans.branch_id -> branches | 0 |
| loans.product_id -> products | 0 |
| loans.borrower_id -> borrowers | 0 |
| snapshot.loan_id -> loans | 0 |

**Finding:** repayments.loan_id -> loans: 60

### P-08: Date sanity

_Why:_ Payments must fall between the loan's disbursement date and the as-of date (2026-06-30).

| first_txn | last_txn | before_disbursement | after_as_of |
|---|---|---|---|
| 2024-01-27 | 2026-08-24 | 30 | 12 |

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
| 2024-01-01 | 219,122.00 | 223,755.00 | 2.11 |
| 2024-03-01 | 10,816,370.00 | 11,113,456.00 | 2.75 |
| 2025-08-01 | 107,943,222.00 | 104,798,305.00 | -2.91 |
| 2025-10-01 | 116,508,468.00 | 4,616,918,169.00 | 3,862.73 |
| 2025-11-01 | 117,519,461.00 | 4,837,987,471.00 | 4,016.75 |
| 2025-12-01 | 125,175,531.00 | 5,214,328,734.00 | 4,065.61 |
| 2026-01-01 | 127,095,249.00 | 5,331,862,331.00 | 4,095.17 |
| 2026-02-01 | 124,196,027.00 | 5,390,275,152.00 | 4,240.13 |
| 2026-03-01 | 139,815,166.00 | 6,144,987,439.00 | 4,295.08 |
| 2026-04-01 | 134,763,326.00 | 6,067,287,962.00 | 4,402.18 |
| 2026-05-01 | 141,892,456.00 | 6,466,872,514.00 | 4,457.59 |
| 2026-06-01 | 139,955,611.00 | 6,437,512,420.00 | 4,499.68 |
| 2026-07-01 | None | 385,573.00 | None |
| 2026-08-01 | None | 449,262.00 | None |

**Finding:** 14 months where the transaction file and the loan snapshot disagree by more than 1%.
