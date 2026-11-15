{#
  By default dbt writes custom schemas as <target>_<custom> (e.g. staging_marts).
  This override uses the custom schema name exactly, so models land in the
  BigQuery datasets we created: `staging` and `marts`.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
