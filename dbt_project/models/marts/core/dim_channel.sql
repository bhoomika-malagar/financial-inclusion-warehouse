-- One row per payment channel. "Digital" is defined once, here, from the seed.
select
    channel,
    channel_name,
    channel_group,
    cast(is_digital as bool) as is_digital
from {{ ref('channel_mapping') }}
