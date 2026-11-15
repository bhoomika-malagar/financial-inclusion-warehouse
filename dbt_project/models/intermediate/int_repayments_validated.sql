-- One row per unique payment, enriched with loan attributes and validity flags.
-- A payment is valid only if it passes every rule below. Invalid payments are
-- not deleted: they go to audit_repayments_quarantine so they can be reviewed.
with repayments as (
    select * from {{ ref('stg_repayments') }}
),

loans as (
    select l.*, b.segment_id
    from {{ ref('stg_loans') }} l
    left join {{ ref('stg_borrowers') }} b using (borrower_id)
),

flagged as (
    select
        r.*,
        l.branch_id,
        l.product_id,
        l.segment_id,
        l.disbursement_date,
        l.loan_id is null                                    as is_orphan_loan,             -- SI-06
        r.amount_inr <= 0                                    as is_non_positive_amount,     -- SI-05
        r.txn_date < l.disbursement_date                     as is_before_disbursement,     -- SI-07
        r.txn_date > date '{{ var("as_of_date") }}'          as is_after_as_of_date         -- SI-11
    from repayments r
    left join loans l on r.loan_id = l.loan_id
)

select
    *,
    case
        when is_orphan_loan          then 'Unknown loan_id'
        when is_non_positive_amount  then 'Zero or negative amount'
        when is_before_disbursement  then 'Paid before disbursement'
        when is_after_as_of_date     then 'Dated after as-of date'
    end                                                       as rejection_reason,
    not (is_orphan_loan or is_non_positive_amount
         or coalesce(is_before_disbursement, false)
         or is_after_as_of_date)                              as is_valid
from flagged
