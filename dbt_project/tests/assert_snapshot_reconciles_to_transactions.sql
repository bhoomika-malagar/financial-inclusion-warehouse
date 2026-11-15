-- Two systems report the same collections: the loan-management snapshot and
-- the payment transaction feed. After cleaning, monthly totals must agree
-- within 1%. Months that do not agree point to missing or extra payments.
{{ config(severity='warn', meta={'seeded_issue': 'SI-02'}) }}

with snapshot as (
    select date_trunc(snapshot_month, month) as month, sum(amount_paid_in_month) as snapshot_paid
    from {{ ref('fct_loan_repayment_monthly') }}
    group by 1
),

transactions as (
    select txn_month as month, sum(amount_inr) as txn_paid
    from {{ ref('fct_repayment_transaction') }}
    group by 1
)

select
    month,
    snapshot_paid,
    txn_paid,
    round(100 * (txn_paid - snapshot_paid) / snapshot_paid, 2) as diff_pct
from snapshot
join transactions using (month)
where abs(txn_paid - snapshot_paid) > 0.01 * snapshot_paid
