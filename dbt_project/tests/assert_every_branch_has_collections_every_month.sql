-- SI-02: every branch should collect payments in every month between its first
-- and last month of activity. A gap usually means a file never arrived.
-- Warn, not error: missing data cannot be recreated by SQL; it must be
-- requested again from the branch.
{{ config(severity='warn', meta={'seeded_issue': 'SI-02'}) }}

with branch_months as (
    select branch_id, txn_month, count(*) as payments
    from {{ ref('fct_repayment_transaction') }}
    group by 1, 2
),

span as (
    select branch_id, min(txn_month) as first_month, max(txn_month) as last_month
    from branch_months
    group by 1
),

expected as (
    select branch_id, month
    from span, unnest(generate_date_array(first_month, last_month, interval 1 month)) as month
)

select e.branch_id, e.month as missing_month
from expected e
left join branch_months b
  on e.branch_id = b.branch_id and e.month = b.txn_month
where b.branch_id is null
