-- Totals reconcile to raw: every unique raw payment must end up in exactly one
-- place, the transaction fact or the quarantine table, with the same rupee
-- amount. Recomputed here from raw, independently of the staging model.
with raw_unique as (
    select
        txn_id,
        any_value(case
            when source_system = '{{ var("upi_paise_source") }}'
             and txn_date >= date '{{ var("upi_paise_from_date") }}'
                then amount / 100
            else amount
        end) as amount_inr
    from {{ source('raw', 'repayments') }}
    group by txn_id
),

raw_totals as (
    select count(*) as n, round(sum(amount_inr), 2) as amount from raw_unique
),

warehouse_totals as (
    select count(*) as n, round(sum(amount_inr), 2) as amount
    from (
        select txn_id, amount_inr from {{ ref('fct_repayment_transaction') }}
        union all
        select txn_id, amount_inr from {{ ref('audit_repayments_quarantine') }}
    )
)

select r.n as raw_rows, w.n as warehouse_rows, r.amount as raw_amount, w.amount as warehouse_amount
from raw_totals r cross join warehouse_totals w
where r.n != w.n or abs(r.amount - w.amount) > 1
