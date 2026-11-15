-- One row per branch. State is an attribute (hierarchy: state > branch).
select
    branch_id,
    branch_name,
    state,
    opened_date
from {{ ref('stg_branches') }}
