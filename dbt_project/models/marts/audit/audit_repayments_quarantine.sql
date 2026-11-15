-- Payments rejected by validation, with the reason. Not used by KPIs;
-- this is the review list for the operations team.
select
    txn_id,
    loan_id,
    txn_date,
    amount_raw,
    amount_inr,
    channel,
    source_system,
    rejection_reason
from {{ ref('int_repayments_validated') }}
where not is_valid
