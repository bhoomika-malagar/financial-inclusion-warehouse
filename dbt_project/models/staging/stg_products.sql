-- One row per loan product.
select
    product_id,
    product_name,
    product_category,
    annual_interest_rate,
    min_amount,
    max_amount
from {{ source('raw', 'products') }}
