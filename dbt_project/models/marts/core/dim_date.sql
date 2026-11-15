-- One row per calendar day.
select
    d                                         as date_day,
    extract(year from d)                      as year,
    extract(quarter from d)                   as quarter,
    extract(month from d)                     as month,
    format_date('%B', d)                      as month_name,
    format_date('%Y-%m', d)                   as year_month,
    date_trunc(d, month)                      as month_start,
    last_day(d, month)                        as month_end,
    d = last_day(d, month)                    as is_month_end
from unnest(generate_date_array(
    date '{{ var("date_spine_start") }}',
    date '{{ var("date_spine_end") }}'
)) as d
