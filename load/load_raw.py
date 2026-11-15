"""
Stage 2a: Load the generated CSV files into BigQuery (dataset: raw).

Design choices
--------------
* The raw layer is a faithful copy of the source files: no cleaning, no fixes.
  All cleaning happens later in dbt staging models, so every fix is visible,
  versioned and testable.
* Each table has an EXPLICIT schema (no auto-detect). Auto-detect guesses types
  from a sample and can silently turn IDs into numbers or dates into strings.
  An explicit schema is the "contract" for what the source system sends.
* WRITE_TRUNCATE: re-running the script replaces the tables, so loading is
  repeatable (idempotent) and never double-loads data.

Run:  python load/load_raw.py
"""

from __future__ import annotations

import os
from pathlib import Path

from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

PROJECT = os.environ.get("GCP_PROJECT", "fin-inclusion-dwh")
DATASET = "raw"
LOCATION = "asia-south1"

S, I, F, D, DT = "STRING", "INT64", "FLOAT64", "DATE", "DATETIME"

SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "branches": [("branch_id", S), ("branch_name", S), ("state", S), ("opened_date", D)],
    "products": [
        ("product_id", S), ("product_name", S), ("product_category", S),
        ("annual_interest_rate", F), ("min_amount", I), ("max_amount", I),
    ],
    "borrowers": [
        ("borrower_id", S), ("branch_id", S), ("segment_id", S),
        ("segment_name", S), ("gender", S), ("age_at_onboarding", I),
    ],
    "loans": [
        ("loan_id", S), ("borrower_id", S), ("branch_id", S), ("product_id", S),
        ("disbursement_date", D), ("principal_amount", I), ("annual_interest_rate", F),
        ("tenure_months", I), ("emi_amount", F), ("last_updated_at", DT),
    ],
    "repayment_schedule": [
        ("loan_id", S), ("instalment_no", I), ("due_date", D),
        ("amount_due", F), ("principal_component", F), ("interest_component", F),
    ],
    "loan_monthly_snapshot": [
        ("loan_id", S), ("snapshot_month", D), ("loan_status", S),
        ("instalments_due_cum", I), ("instalments_paid_cum", I),
        ("amount_due_in_month", F), ("amount_paid_in_month", F),
        ("principal_outstanding", F), ("days_past_due", I),
    ],
    "repayments": [
        ("txn_id", S), ("loan_id", S), ("txn_date", D),
        ("amount", F), ("channel", S), ("source_system", S),
    ],
}


def main() -> None:
    client = bigquery.Client(project=PROJECT, location=LOCATION)
    print(f"Loading into {PROJECT}.{DATASET} ({LOCATION})\n")

    for table, cols in SCHEMAS.items():
        path = RAW_DIR / f"{table}.csv"
        if not path.exists():
            raise FileNotFoundError(f"{path} not found. Run generator/generate_data.py first.")

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=[bigquery.SchemaField(name, typ) for name, typ in cols],
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        table_id = f"{PROJECT}.{DATASET}.{table}"
        with open(path, "rb") as fh:
            job = client.load_table_from_file(fh, table_id, job_config=job_config)
        job.result()  # wait; raises if the load failed

        loaded = client.get_table(table_id).num_rows
        csv_rows = sum(1 for _ in open(path, encoding="utf-8")) - 1
        status = "OK" if loaded == csv_rows else "ROW COUNT MISMATCH"
        print(f"  {table:<24}{loaded:>12,} rows   (csv: {csv_rows:,})  {status}")

    print("\nDone.")


if __name__ == "__main__":
    main()
