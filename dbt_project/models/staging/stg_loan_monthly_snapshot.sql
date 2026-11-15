-- One row per loan per month-end, as reported by the loan-management system.
-- No fixes here: SI-09 (paid > due) cannot be corrected safely, so it is
-- flagged by a test instead of being silently changed.
select
    loan_id,
    snapshot_month,
    loan_status,
    instalments_due_cum,
    instalments_paid_cum,
    amount_due_in_month,
    amount_paid_in_month,
    principal_outstanding,
    days_past_due
from {{ source('raw', 'loan_monthly_snapshot') }}
