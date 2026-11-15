-- Grain: one row per valid, de-duplicated payment transaction.
-- Duplicates, unit errors and invalid payments were handled upstream.
select
    v.txn_id,
    v.loan_id,
    v.txn_date,
    date_trunc(v.txn_date, month)   as txn_month,
    v.branch_id,
    v.product_id,
    v.segment_id,
    v.channel,
    c.is_digital,
    v.source_system,
    v.amount_inr
from {{ ref('int_repayments_validated') }} v
left join {{ ref("dim_channel") }} c on v.channel = c.channel
where v.is_valid
