-- One row per unique payment transaction (still includes invalid payments;
-- validation happens in int_repayments_validated).
--
-- Fixes applied here:
--   SI-01  exact duplicate rows      -> keep one row per txn_id
--   SI-03  paise from upi_gateway    -> convert to rupees from the cut-over date
--   SI-08  missing channel           -> 'UNKNOWN' (kept, not dropped)
select
    txn_id,
    loan_id,
    txn_date,
    channel                                             as channel_raw,
    coalesce(channel, 'UNKNOWN')                        as channel,
    source_system,
    amount                                              as amount_raw,
    case
        when source_system = '{{ var("upi_paise_source") }}'
         and txn_date >= date '{{ var("upi_paise_from_date") }}'
            then amount / 100
        else amount
    end                                                 as amount_inr,
    (source_system = '{{ var("upi_paise_source") }}'
     and txn_date >= date '{{ var("upi_paise_from_date") }}') as was_converted_from_paise
from {{ source('raw', 'repayments') }}
where true
qualify row_number() over (partition by txn_id order by txn_id) = 1
