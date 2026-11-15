# KPI Definitions

All KPIs are calculated in dbt (`dbt_project/models/marts/kpi/`) from the two fact tables,
so the dashboard only displays them and never recalculates business logic.
Reporting date (as-of): **30 June 2026**. Amounts are in Indian rupees (₹).

**Common terms**

* **Month-end snapshot**: the state of every loan on the last day of a month (`fct_loan_repayment_monthly`).
* **Outstanding principal (OS)**: principal not yet repaid on that date.
* **DPD (days past due)**: days since the oldest unpaid instalment fell due; 0 if nothing is overdue.
* **Gross loan portfolio (GLP)**: Σ OS of all loans on the book at month-end. Written-off loans
  (DPD > 180) have left the book and are excluded.

---

### 1. Portfolio at Risk over 30 days (PAR30)

$$\text{PAR30}_m = \frac{\sum \text{OS of loans with DPD} > 30 \text{ at month-end } m}{\text{GLP}_m} \times 100$$

* Uses the **whole outstanding balance** of an overdue loan, not just the overdue instalments
  (industry convention: once a loan is late, all of it is at risk).
* Excludes written-off loans from numerator and denominator.
* Model: `kpi_portfolio_summary.par30_pct`; by branch/product from `kpi_portfolio_monthly` as
  Σ `par30_outstanding` / Σ `gross_loan_portfolio`.
* Value at 30 Jun 2026: **4.01 %**

### 2. Portfolio at Risk over 90 days (PAR90)

$$\text{PAR90}_m = \frac{\sum \text{OS of loans with DPD} > 90 \text{ at month-end } m}{\text{GLP}_m} \times 100$$

* Same rules as PAR30 with a 90-day threshold. PAR90 ≤ PAR30 always (tested).
* Value at 30 Jun 2026: **1.24 %**

### 3. Collection efficiency (CE)

$$\text{CE}_m = \frac{\sum \text{amount collected in month } m}{\sum \text{amount due in month } m} \times 100$$

* **Due**: EMIs whose due date falls in month *m*. **Collected**: all repayments received in
  month *m*, as reported by the loan-management snapshot.
* Collections include arrears paid late, so CE can exceed 100 % in a month when borrowers catch up.
* Source is the loan-management snapshot, not the transaction feed, so it is unaffected by
  the missing BR012 file for August 2025.
* Value for June 2026: **95.70 %**

### 4. Repayment vintage curve

For a cohort *c* (all loans disbursed in the same calendar month), at age *k* months since disbursement:

$$\text{Cumulative repayment}_{c,k} = \frac{\sum_{i=1}^{k} \text{collected}_{c,i}}{\sum_{i=1}^{k} \text{due}_{c,i}} \times 100$$

* **Due** comes from the contractual EMI schedule, so a written-off loan keeps counting as due
  and the curve shows the real loss. **Collected** comes from the monthly snapshot.
* Only ages up to the as-of date are shown (no future dues).
* Also reported: cumulative collected as % of amount disbursed (`cumulative_paid_pct_of_disbursed`).
* Model: `kpi_vintage_curves`. Typical level: 95–97 % after 6 months.

### 5. Digital share of collections

$$\text{Digital share (value)}_m = \frac{\sum \text{amount via UPI, bank transfer, NACH}}{\sum \text{amount via digital + cash}} \times 100$$

$$\text{Digital share (count)}_m = \frac{\text{number of digital payments}}{\text{number of digital + cash payments}} \times 100$$

* "Digital" = every channel except cash, defined once in `dim_channel` (seed `channel_mapping.csv`).
* Payments with no recorded channel (`UNKNOWN`) are excluded from both numerator and denominator.
* All amounts use `amount_inr`: the upi_gateway values sent in paise from Oct 2025 are divided by 100.
* Value for June 2026: **77.18 % by value, 75.38 % by count**

### 6. Growth of digital collections

| Measure | Formula | Column |
|---|---|---|
| Share change MoM (pp) | share*m* − share*m−1* | `share_value_mom_pp` |
| Share change YoY (pp) | share*m* − share*m−12* | `share_value_yoy_pp` |
| Digital value growth MoM (%) | (digital ₹*m* / digital ₹*m−1* − 1) × 100 | `digital_value_mom_growth_pct` |
| Digital value growth YoY (%) | (digital ₹*m* / digital ₹*m−12* − 1) × 100 | `digital_value_yoy_growth_pct` |

The same four measures exist for payment counts. **Use the share change (pp) to judge adoption.**
Growth in rupees mixes adoption with portfolio growth: in early 2025 YoY value growth looks like
+43,000 % only because January 2024 had 59 payments while the book was being built.

### 7. Average payment size by channel

$$\text{Average payment}_{m,ch} = \frac{\sum \text{amount\_inr of payments in channel } ch \text{ in month } m}{\text{number of those payments}}$$

* Model: `kpi_channel_monthly`. Uses rupees after the paise fix; without the fix, UPI's
  average would jump ~100× from October 2025.
