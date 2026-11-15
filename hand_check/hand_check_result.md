# Hand check: PAR30 at 30 June 2026

Recomputed from the raw CSV files with Python (polars) only: no BigQuery, no dbt models.

## Step-by-step calculation

1. Snapshot rows at 2026-06-30: **38,056** loans
2. Excluding loans written off this month: **37,939** loans remain on the book
3. Gross loan portfolio = Σ outstanding principal = **₹1,366,877,076.67**
4. Loans with DPD > 30: **1,068**, their outstanding = **₹41,731,857.51**
5. PAR30 = 41,731,857.51 / 1,366,877,076.67 × 100 = **3.05 %**

## One overdue loan, by hand

Loan **LN0004065**, from the raw schedule and snapshot:

* Instalments due by 2026-06-30: **27** (counted from repayment_schedule.csv)
* Instalments paid: **25**, so the oldest unpaid is instalment **#26**, due **2026-05-28**
* DPD = 2026-06-30 − 2026-05-28 = **33 days** (snapshot says 33)
* 33 > 30, so all of its outstanding principal (₹27,676.01) counts in the PAR30 numerator.

## Result

| Check | Hand calculation | Dashboard / pipeline | Match |
|---|---|---|---|
| PAR30, whole portfolio, Jun 2026 | 3.05 % | 3.05 % | ✅ |
| PAR30, Bihar, Jun 2026 | 4.52 % | 4.52 % | ✅ |
| DPD of loan LN0004065 | 33 | 33 | ✅ |

The independent calculation reproduces the dashboard, which shows the pipeline (load → staging → facts → KPI model → dashboard) carries the numbers through correctly.
