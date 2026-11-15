-- One row per loan instalment due.
select
    loan_id,
    instalment_no,
    due_date,
    amount_due,
    principal_component,
    interest_component
from {{ source('raw', 'repayment_schedule') }}
