-- Payments by channel per month, including average payment size.
-- Grain: one row per calendar month x channel.
-- Amounts are amount_inr (rupees), so the paise problem from upi_gateway is
-- already corrected and averages are comparable across channels.
select
    f.txn_month                              as month,
    f.channel,
    c.channel_name,
    c.channel_group,
    count(*)                                 as payments,
    sum(f.amount_inr)                        as amount_inr,
    round(sum(f.amount_inr) / count(*), 2)   as avg_payment_inr
from {{ ref('fct_repayment_transaction') }} f
join {{ ref('dim_channel') }} c on f.channel = c.channel
group by 1, 2, 3, 4
