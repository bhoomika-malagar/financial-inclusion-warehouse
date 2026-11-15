-- Every payment in the fact must fall on or after its loan's disbursement date.
select f.txn_id, f.txn_date, l.disbursement_date
from {{ ref('fct_repayment_transaction') }} f
join {{ ref('stg_loans') }} l on f.loan_id = l.loan_id
where f.txn_date < l.disbursement_date
