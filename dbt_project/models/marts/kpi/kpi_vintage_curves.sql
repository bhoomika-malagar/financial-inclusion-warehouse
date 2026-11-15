-- Repayment vintage curves.
-- Grain: one row per disbursement-month cohort x months since disbursement.
--
-- cumulative_repayment_pct = cumulative amount collected / cumulative amount due,
-- for loans disbursed in the same month, measured k months after disbursement.
-- A healthy cohort stays close to 100%; a cohort that drifts down is repaying
-- less of what it owes as it ages.
--
-- Amount due comes from the contractual schedule (so written-off loans keep
-- counting as "due"); amount collected comes from the loan-management snapshot.
with loans as (
    select loan_id, disbursement_month, principal_amount
    from {{ ref('stg_loans') }}
),

cohorts as (
    select disbursement_month, count(*) as loans_disbursed, sum(principal_amount) as amount_disbursed
    from loans
    group by 1
),

due as (
    select
        l.disbursement_month,
        date_diff(date_trunc(s.due_date, month), l.disbursement_month, month) as months_since_disbursement,
        sum(s.amount_due) as amount_due
    from {{ ref('stg_repayment_schedule') }} s
    join loans l on s.loan_id = l.loan_id
    where s.due_date <= date '{{ var("as_of_date") }}'
    group by 1, 2
),

paid as (
    select disbursement_month, months_since_disbursement, sum(amount_paid_in_month) as amount_paid
    from {{ ref('fct_loan_repayment_monthly') }}
    group by 1, 2
),

joined as (
    select
        coalesce(d.disbursement_month, p.disbursement_month)                 as disbursement_month,
        coalesce(d.months_since_disbursement, p.months_since_disbursement)   as months_since_disbursement,
        coalesce(d.amount_due, 0)                                            as amount_due,
        coalesce(p.amount_paid, 0)                                           as amount_paid
    from due d
    full outer join paid p
      on d.disbursement_month = p.disbursement_month
     and d.months_since_disbursement = p.months_since_disbursement
)

select
    j.disbursement_month,
    format_date('%Y-%m', j.disbursement_month)                                as cohort,
    concat(cast(extract(year from j.disbursement_month) as string), '-Q', cast(extract(quarter from j.disbursement_month) as string)) as cohort_quarter,
    j.months_since_disbursement,
    c.loans_disbursed,
    c.amount_disbursed,
    j.amount_due,
    j.amount_paid,
    sum(j.amount_due)  over w                                                 as cumulative_due,
    sum(j.amount_paid) over w                                                 as cumulative_paid,
    round(100 * safe_divide(sum(j.amount_paid) over w, sum(j.amount_due) over w), 2) as cumulative_repayment_pct,
    round(100 * safe_divide(sum(j.amount_paid) over w, c.amount_disbursed), 2)       as cumulative_paid_pct_of_disbursed
from joined j
join cohorts c on j.disbursement_month = c.disbursement_month
where j.months_since_disbursement >= 1
window w as (partition by j.disbursement_month order by j.months_since_disbursement
             rows between unbounded preceding and current row)
