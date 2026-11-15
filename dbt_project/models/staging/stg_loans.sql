-- One row per loan. Fixes SI-04: the source re-sends a loan record when it is
-- edited, so the same loan_id can appear more than once. Keep the latest version.
select
    loan_id,
    borrower_id,
    branch_id,
    product_id,
    disbursement_date,
    date_trunc(disbursement_date, month)  as disbursement_month,
    principal_amount,
    annual_interest_rate,
    tenure_months,
    emi_amount,
    last_updated_at
from {{ source('raw', 'loans') }}
where true
qualify row_number() over (partition by loan_id order by last_updated_at desc) = 1
