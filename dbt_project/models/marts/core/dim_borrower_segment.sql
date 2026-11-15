-- One row per borrower segment.
select distinct
    segment_id,
    segment_name
from {{ ref('stg_borrowers') }}
