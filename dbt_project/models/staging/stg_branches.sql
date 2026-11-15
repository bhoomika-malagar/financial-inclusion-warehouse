-- One row per branch. Fixes SI-10: state labels are trimmed and title-cased
-- so "karnataka " and "Karnataka" become the same state.
select
    branch_id,
    branch_name,
    initcap(trim(state))  as state,
    state                 as state_raw,   -- kept for audit
    opened_date
from {{ source('raw', 'branches') }}
