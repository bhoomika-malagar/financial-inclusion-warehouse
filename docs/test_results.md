# Data Quality Test Results

Generated 2026-11-16 02:37 from `dbt test`.

**74 tests:** PASS = 61, WARN = 13

Tests run at three layers:

* **Raw source** (severity warn): detect problems in what the source systems send.
* **Staging** (severity error): prove each cleaning step worked.
* **Mart** (severity error, two business checks warn): guarantee what the dashboard reads.

## Seeded issues: caught or missed

| Issue | Description | Caught? | Test(s) that caught it | Failing rows |
|---|---|---|---|---|
| SI-01 | Duplicate transaction rows | ✅ Caught | `raw_repayment_txn_id_unique` | 1,200 |
| SI-02 | Missing month for one branch | ✅ Caught | `assert_every_branch_has_collections_every_month`<br>`assert_snapshot_reconciles_to_transactions` | 1<br>1 |
| SI-03 | Amounts in different units from one source | ✅ Caught | `assert_raw_payment_size_plausible` | 143,158 |
| SI-04 | Duplicate loan IDs | ✅ Caught | `raw_loan_id_unique` | 25 |
| SI-05 | Negative amounts | ✅ Caught | `raw_repayment_amount_not_negative` | 40 |
| SI-06 | Orphan loan IDs | ✅ Caught | `raw_repayment_loan_id_exists_in_loans` | 61 |
| SI-07 | Payment before disbursement | ✅ Caught | `assert_raw_payment_not_before_disbursement` | 30 |
| SI-08 | Missing payment channel | ✅ Caught | `raw_repayment_channel_not_null` | 251 |
| SI-09 | Instalments paid exceed instalments due | ✅ Caught | `raw_snapshot_paid_not_above_due`<br>`fct_monthly_paid_not_above_due` | 15<br>15 |
| SI-10 | Inconsistent state label | ✅ Caught | `raw_branch_state_in_known_list` | 1 |
| SI-11 | Future-dated transactions | ✅ Caught | `raw_repayment_not_after_as_of_date` | 12 |

## All tests

| Layer | Test | Type | Severity | Status | Failing rows | Seeded issue |
|---|---|---|---|---|---|---|
| Raw source | `assert_raw_payment_not_before_disbursement` | Custom SQL | WARN | ⚠️ WARN | 30 | SI-07 |
| Raw source | `assert_raw_payment_size_plausible` | Custom SQL | WARN | ⚠️ WARN | 143,158 | SI-03 |
| Raw source | `raw_branch_state_in_known_list` | Generic | WARN | ⚠️ WARN | 1 | SI-10 |
| Raw source | `raw_loan_id_unique` | Generic | WARN | ⚠️ WARN | 25 | SI-04 |
| Raw source | `raw_repayment_amount_not_negative` | Generic | WARN | ⚠️ WARN | 40 | SI-05 |
| Raw source | `raw_repayment_channel_not_null` | Generic | WARN | ⚠️ WARN | 251 | SI-08 |
| Raw source | `raw_repayment_loan_id_exists_in_loans` | Generic | WARN | ⚠️ WARN | 61 | SI-06 |
| Raw source | `raw_repayment_not_after_as_of_date` | Generic | WARN | ⚠️ WARN | 12 | SI-11 |
| Raw source | `raw_repayment_txn_id_unique` | Generic | WARN | ⚠️ WARN | 1,200 | SI-01 |
| Raw source | `raw_snapshot_paid_not_above_due` | Generic | WARN | ⚠️ WARN | 15 | SI-09 |
| Staging | `dbt_utils_accepted_range_kpi_digital_collections_monthly_digital_share_value_pct__100__0` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `dbt_utils_accepted_range_kpi_portfolio_summary_par30_pct__100__0` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `dbt_utils_unique_combination_of_columns_kpi_channel_monthly_month__channel` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `dbt_utils_unique_combination_of_columns_kpi_portfolio_monthly_snapshot_month__branch_id__product_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `dbt_utils_unique_combination_of_columns_kpi_vintage_curves_disbursement_month__months_since_disbursement` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `kpi_par_outstanding_within_portfolio` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `not_null_kpi_digital_collections_monthly_month` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `not_null_kpi_portfolio_summary_snapshot_month` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `not_null_stg_branches_branch_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `not_null_stg_loans_loan_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `not_null_stg_repayments_channel` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `not_null_stg_repayments_txn_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `stg_branch_state_in_known_list` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `stg_repayment_channel_in_mapping` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `unique_kpi_digital_collections_monthly_month` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `unique_kpi_portfolio_summary_snapshot_month` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `unique_stg_branches_branch_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `unique_stg_loans_loan_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Staging | `unique_stg_repayments_txn_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `assert_every_branch_has_collections_every_month` | Custom SQL | WARN | ⚠️ WARN | 1 | SI-02 |
| Mart | `assert_snapshot_reconciles_to_transactions` | Custom SQL | WARN | ⚠️ WARN | 1 | SI-02 |
| Mart | `fct_monthly_paid_not_above_due` | Generic | WARN | ⚠️ WARN | 15 | SI-09 |
| Mart | `accepted_values_fct_loan_repayment_monthly_loan_status__ACTIVE__CLOSED__WRITTEN_OFF` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `assert_fct_monthly_matches_snapshot_rows` | Custom SQL | ERROR | ✅ PASS | 0 |  |
| Mart | `assert_fct_payment_within_loan_life` | Custom SQL | ERROR | ✅ PASS | 0 |  |
| Mart | `assert_transaction_totals_reconcile_to_raw` | Custom SQL | ERROR | ✅ PASS | 0 |  |
| Mart | `dbt_utils_unique_combination_of_columns_fct_loan_repayment_monthly_loan_id__snapshot_month` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `dim_branch_state_in_known_list` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `fct_monthly_dpd_not_negative` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `fct_monthly_outstanding_within_principal` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `fct_txn_amount_positive` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `fct_txn_not_after_as_of_date` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_dim_borrower_segment_segment_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_dim_branch_branch_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_dim_branch_state` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_dim_channel_channel` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_dim_channel_is_digital` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_dim_date_date_day` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_dim_product_product_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_loan_repayment_monthly_branch_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_loan_repayment_monthly_loan_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_loan_repayment_monthly_product_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_loan_repayment_monthly_segment_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_loan_repayment_monthly_snapshot_month` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_repayment_transaction_is_digital` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_repayment_transaction_loan_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `not_null_fct_repayment_transaction_txn_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_loan_repayment_monthly_branch_id__branch_id__ref_dim_branch_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_loan_repayment_monthly_disbursement_month__date_day__ref_dim_date_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_loan_repayment_monthly_product_id__product_id__ref_dim_product_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_loan_repayment_monthly_segment_id__segment_id__ref_dim_borrower_segment_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_loan_repayment_monthly_snapshot_month__date_day__ref_dim_date_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_repayment_transaction_branch_id__branch_id__ref_dim_branch_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_repayment_transaction_channel__channel__ref_dim_channel_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_repayment_transaction_loan_id__loan_id__ref_stg_loans_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_repayment_transaction_product_id__product_id__ref_dim_product_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_repayment_transaction_segment_id__segment_id__ref_dim_borrower_segment_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `relationships_fct_repayment_transaction_txn_date__date_day__ref_dim_date_` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `unique_dim_borrower_segment_segment_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `unique_dim_branch_branch_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `unique_dim_channel_channel` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `unique_dim_date_date_day` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `unique_dim_product_product_id` | Generic | ERROR | ✅ PASS | 0 |  |
| Mart | `unique_fct_repayment_transaction_txn_id` | Generic | ERROR | ✅ PASS | 0 |  |
