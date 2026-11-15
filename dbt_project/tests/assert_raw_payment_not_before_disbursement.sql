-- SI-07: a payment cannot happen before its loan was disbursed.
-- Runs on raw data, so it reports what the source sent.
{{ config(severity='warn', meta={'seeded_issue': 'SI-07'}) }}

select r.txn_id, r.loan_id, r.txn_date, l.disbursement_date
from {{ source('raw', 'repayments') }} r
join (
    select loan_id, min(disbursement_date) as disbursement_date
    from {{ source('raw', 'loans') }}
    group by loan_id
) l on r.loan_id = l.loan_id
where r.txn_date < l.disbursement_date
