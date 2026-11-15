-- One row per borrower.
select
    borrower_id,
    branch_id,
    segment_id,
    segment_name,
    gender,
    age_at_onboarding
from {{ source('raw', 'borrowers') }}
