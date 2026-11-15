-- Portfolio health and collection building blocks.
-- Grain: one row per month-end x branch x product.
-- Only ADDITIVE measures are stored (sums and counts). Ratios such as PAR30 or
-- collection efficiency are calculated from these sums at whatever level the
-- dashboard filters to: sum(par30_outstanding) / sum(gross_loan_portfolio).
-- Averaging pre-computed ratios across branches would give the wrong answer.
select
    f.snapshot_month,
    b.state,
    f.branch_id,
    b.branch_name,
    f.product_id,
    p.product_name,

    -- Portfolio at risk (written-off loans have left the book and are excluded)
    countif(f.loan_status != 'WRITTEN_OFF' and f.principal_outstanding > 0)          as active_loans,
    sum(if(f.loan_status != 'WRITTEN_OFF', f.principal_outstanding, 0))              as gross_loan_portfolio,
    sum(if(f.loan_status != 'WRITTEN_OFF' and f.is_par30, f.principal_outstanding, 0)) as par30_outstanding,
    sum(if(f.loan_status != 'WRITTEN_OFF' and f.is_par90, f.principal_outstanding, 0)) as par90_outstanding,
    sum(if(f.loan_status = 'WRITTEN_OFF', f.principal_outstanding, 0))               as written_off_amount,

    -- Collection efficiency
    sum(f.amount_due_in_month)                                                       as amount_due,
    sum(f.amount_paid_in_month)                                                      as amount_collected
from {{ ref('fct_loan_repayment_monthly') }} f
join {{ ref('dim_branch') }} b on f.branch_id = b.branch_id
join {{ ref('dim_product') }} p on f.product_id = p.product_id
group by 1, 2, 3, 4, 5, 6
