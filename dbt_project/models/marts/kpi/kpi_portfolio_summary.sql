-- Company-level KPIs per month, with ratios calculated.
-- Grain: one row per month-end.
select
    snapshot_month,
    sum(active_loans)                                                     as active_loans,
    sum(gross_loan_portfolio)                                             as gross_loan_portfolio,
    sum(par30_outstanding)                                                as par30_outstanding,
    sum(par90_outstanding)                                                as par90_outstanding,
    round(100 * safe_divide(sum(par30_outstanding), sum(gross_loan_portfolio)), 2) as par30_pct,
    round(100 * safe_divide(sum(par90_outstanding), sum(gross_loan_portfolio)), 2) as par90_pct,
    sum(amount_due)                                                       as amount_due,
    sum(amount_collected)                                                 as amount_collected,
    round(100 * safe_divide(sum(amount_collected), sum(amount_due)), 2)   as collection_efficiency_pct
from {{ ref('kpi_portfolio_monthly') }}
group by 1
