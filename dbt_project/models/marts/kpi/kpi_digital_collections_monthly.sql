-- Digital share of collections, with month-on-month and year-on-year growth.
-- Grain: one row per calendar month.
--
-- Digital = UPI, bank transfer, NACH (dim_channel.is_digital). Payments with an
-- unrecorded channel (UNKNOWN) are excluded from both numerator and denominator
-- of the share, because we cannot say which side they belong to.
with monthly as (
    select
        f.txn_month                                                          as month,
        count(*)                                                             as payments_total,
        sum(f.amount_inr)                                                    as amount_total,
        countif(c.channel_group = 'Digital')                                 as payments_digital,
        sum(if(c.channel_group = 'Digital', f.amount_inr, 0))                as amount_digital,
        countif(c.channel_group = 'Cash')                                    as payments_cash,
        sum(if(c.channel_group = 'Cash', f.amount_inr, 0))                   as amount_cash,
        countif(c.channel_group = 'Unknown')                                 as payments_unknown
    from {{ ref('fct_repayment_transaction') }} f
    join {{ ref('dim_channel') }} c on f.channel = c.channel
    group by 1
),

shares as (
    select
        *,
        round(100 * safe_divide(amount_digital, amount_digital + amount_cash), 2)     as digital_share_value_pct,
        round(100 * safe_divide(payments_digital, payments_digital + payments_cash), 2) as digital_share_count_pct
    from monthly
)

select
    *,
    -- Change in the share itself, in percentage points
    round(digital_share_value_pct - lag(digital_share_value_pct, 1)  over (order by month), 2) as share_value_mom_pp,
    round(digital_share_value_pct - lag(digital_share_value_pct, 12) over (order by month), 2) as share_value_yoy_pp,
    round(digital_share_count_pct - lag(digital_share_count_pct, 1)  over (order by month), 2) as share_count_mom_pp,
    round(digital_share_count_pct - lag(digital_share_count_pct, 12) over (order by month), 2) as share_count_yoy_pp,
    -- Growth of digital collections, in percent
    round(100 * (safe_divide(amount_digital,   lag(amount_digital, 1)    over (order by month)) - 1), 2) as digital_value_mom_growth_pct,
    round(100 * (safe_divide(amount_digital,   lag(amount_digital, 12)   over (order by month)) - 1), 2) as digital_value_yoy_growth_pct,
    round(100 * (safe_divide(payments_digital, lag(payments_digital, 1)  over (order by month)) - 1), 2) as digital_count_mom_growth_pct,
    round(100 * (safe_divide(payments_digital, lag(payments_digital, 12) over (order by month)) - 1), 2) as digital_count_yoy_growth_pct
from shares
