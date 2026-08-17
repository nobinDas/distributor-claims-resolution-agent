"""
create_bigquery_tables.py

Creates the BigQuery dataset and tables for the UNFI Supplier Deduction &
Claims Resolution Agent capstone project.

Tables created:
    suppliers
    purchase_orders   (EDI 850)
    shipments         (ASN  - EDI 856)
    receiving         (POD)
    invoices          (EDI 810)
    deduction_codes   (the "Supplier Deduction Key" reference table)
    deduction_claims  (EDI 812 chargebacks / disputes)

Prerequisites:
    1. A Google Cloud project with the BigQuery API enabled.
    2. Authenticated locally, e.g.:
           gcloud auth application-default login
       or run this from Cloud Shell, where auth is automatic.
    3. pip install google-cloud-bigquery

Usage:
    python create_bigquery_tables.py --project YOUR_PROJECT_ID
    python create_bigquery_tables.py --project YOUR_PROJECT_ID --dataset unfi_deductions --location US
"""

import argparse
from google.cloud import bigquery
from google.api_core.exceptions import Conflict


def get_schemas():
    """Returns a dict of table_name -> list[bigquery.SchemaField]."""

    schemas = {}

    schemas["suppliers"] = [
        bigquery.SchemaField("supplier_id", "STRING", mode="REQUIRED",
                              description="Unique supplier identifier"),
        bigquery.SchemaField("supplier_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING",
                              description="East or West - matches UNFI's regional split"),
        bigquery.SchemaField("contact_email", "STRING"),
        bigquery.SchemaField("payment_terms", "STRING",
                              description="e.g. '2/10 net 30'"),
    ]

    schemas["purchase_orders"] = [
        bigquery.SchemaField("po_number", "STRING", mode="REQUIRED",
                              description="Purchase order number (EDI 850)"),
        bigquery.SchemaField("supplier_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("order_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("expected_delivery_date", "DATE"),
        bigquery.SchemaField("item_sku", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("item_description", "STRING"),
        bigquery.SchemaField("quantity_ordered", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("unit_price", "NUMERIC", mode="REQUIRED"),
        bigquery.SchemaField("total_po_amount", "NUMERIC", mode="REQUIRED"),
    ]

    schemas["shipments"] = [
        bigquery.SchemaField("asn_id", "STRING", mode="REQUIRED",
                              description="Advance Shipment Notice ID (EDI 856)"),
        bigquery.SchemaField("po_number", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("ship_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("carrier", "STRING"),
        bigquery.SchemaField("item_sku", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("quantity_shipped", "INTEGER", mode="REQUIRED"),
    ]

    schemas["receiving"] = [
        bigquery.SchemaField("pod_id", "STRING", mode="REQUIRED",
                              description="Proof of Delivery record ID"),
        bigquery.SchemaField("po_number", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("asn_id", "STRING"),
        bigquery.SchemaField("received_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("quantity_received", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("condition_notes", "STRING",
                              description="e.g. 'ok', 'short', 'damaged'"),
    ]

    schemas["invoices"] = [
        bigquery.SchemaField("invoice_number", "STRING", mode="REQUIRED",
                              description="Supplier invoice number (EDI 810)"),
        bigquery.SchemaField("po_number", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("supplier_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("invoice_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("quantity_billed", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("invoice_amount", "NUMERIC", mode="REQUIRED"),
    ]

    schemas["deduction_codes"] = [
        bigquery.SchemaField("code", "STRING", mode="REQUIRED",
                              description="Deduction code, e.g. 'MCB-114'"),
        bigquery.SchemaField("description", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("category", "STRING",
                              description="Shortage, Pricing, Compliance, Early Payment Discount, etc."),
        bigquery.SchemaField("typical_validity_notes", "STRING",
                              description="Guidance on when this code is usually valid vs. disputable"),
    ]

    schemas["deduction_claims"] = [
        bigquery.SchemaField("claim_id", "STRING", mode="REQUIRED",
                              description="Deduction / chargeback claim ID (EDI 812)"),
        bigquery.SchemaField("invoice_number", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("po_number", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("supplier_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("deduction_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("claim_amount", "NUMERIC", mode="REQUIRED"),
        bigquery.SchemaField("claim_date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("dispute_status", "STRING",
                              description="open, disputed, resolved_valid, resolved_invalid"),
        bigquery.SchemaField("dispute_text", "STRING",
                              description="Free-text supplier dispute email content, if any"),
    ]

    return schemas


def create_dataset(client, dataset_id, location):
    dataset_ref = bigquery.Dataset(dataset_id)
    dataset_ref.location = location
    try:
        client.create_dataset(dataset_ref)
        print(f"Created dataset: {dataset_id}")
    except Conflict:
        print(f"Dataset already exists, skipping: {dataset_id}")


def create_tables(client, dataset_id, schemas):
    # Tables that benefit from date partitioning (large, time-based fact tables)
    partition_fields = {
        "invoices": "invoice_date",
        "deduction_claims": "claim_date",
        "shipments": "ship_date",
        "receiving": "received_date",
    }

    for table_name, schema in schemas.items():
        table_ref = f"{dataset_id}.{table_name}"
        table = bigquery.Table(table_ref, schema=schema)

        if table_name in partition_fields:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.MONTH,
                field=partition_fields[table_name],
            )

        try:
            client.create_table(table)
            print(f"Created table: {table_ref}")
        except Conflict:
            print(f"Table already exists, skipping: {table_ref}")


def main():
    parser = argparse.ArgumentParser(description="Create BigQuery tables for the UNFI Claims Resolution Agent")
    parser.add_argument("--project", required=True, help="Your Google Cloud project ID")
    parser.add_argument("--dataset", default="unfi_deductions", help="BigQuery dataset name")
    parser.add_argument("--location", default="US", help="Dataset location, e.g. US or us-central1")
    args = parser.parse_args()

    client = bigquery.Client(project=args.project)
    dataset_id = f"{args.project}.{args.dataset}"

    create_dataset(client, dataset_id, args.location)

    schemas = get_schemas()
    create_tables(client, dataset_id, schemas)

    print("\nDone. Tables created in dataset:", dataset_id)
    print("Next step: run the synthetic data generator to populate these tables.")


if __name__ == "__main__":
    main()