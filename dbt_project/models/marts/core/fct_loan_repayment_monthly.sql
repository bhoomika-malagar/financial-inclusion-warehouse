-- Grain: one row per loan per calendar month-end, from the disbursement month
-- until the loan closes, is written off, or the as-of date.
-- Source: the loan-management system's month-end snapshot.
with snapshot as (
    select * from {{ ref('stg_loan_monthly_snapshot') }}
),

loans as (
    select l.*, b.segment_id
    from {{ ref('stg_loans') }} l
    left join {{ ref('stg_borrowers') }} b using (borrower_id)
)

select
    s.loan_id,
    s.snapshot_month,
    l.branch_id,
    l.product_id,
    l.segment_id,
    l.disbursement_month,
    date_diff(s.snapshot_month, l.disbursement_month, month)   as months_since_disbursement,
    s.loan_status,
    l.principal_amount,
    s.amount_due_in_month,
    s.amount_paid_in_month,
    s.principal_outstanding,
    s.days_past_due,
    s.instalments_due_cum,
    s.instalments_paid_cum,
    case
        when s.days_past_due = 0  then '0 Current'
        when s.days_past_due <= 30 then '1-30'
        when s.days_past_due <= 60 then '31-60'
        when s.days_past_due <= 90 then '61-90'
        else '90+'
    end                                                         as dpd_bucket,
    s.days_past_due > 30                                        as is_par30,
    s.days_past_due > 90                                        as is_par90
from snapshot s
inner join loans l on s.loan_id = l.loan_id
