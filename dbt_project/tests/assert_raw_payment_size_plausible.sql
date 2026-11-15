-- SI-03: a single payment should never be more than 3x the loan's EMI.
-- Row-level checks (not null, > 0) cannot see a unit error, because an amount
-- in paise is still a valid positive number. Comparing it with the EMI can.
{{ config(severity='warn', meta={'seeded_issue': 'SI-03'}) }}

select r.txn_id, r.source_system, r.txn_date, r.amount, l.emi_amount
from {{ source('raw', 'repayments') }} r
join (
    select loan_id, max(emi_amount) as emi_amount
    from {{ source('raw', 'loans') }}
    group by loan_id
) l on r.loan_id = l.loan_id
where r.amount > 3 * l.emi_amount
