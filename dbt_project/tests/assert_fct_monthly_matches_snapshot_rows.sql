-- No fan-out: the monthly fact must have exactly one row per source snapshot
-- row. If a join duplicated loans, this count would be higher.
select fct_rows, source_rows
from (
    select
        (select count(*) from {{ ref('fct_loan_repayment_monthly') }}) as fct_rows,
        (select count(*) from {{ source('raw', 'loan_monthly_snapshot') }}) as source_rows
)
where fct_rows != source_rows
