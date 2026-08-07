"""
tools.py

BigQuery tool functions for the UNFI Supplier Deduction & Claims Resolution
Agent. Each function here is passed directly into the ADK Agent's `tools=[]`
list - ADK reads the type hints and docstring to build the function-calling
schema the LLM uses to decide when and how to call it.

Keep docstrings clear and literal: the model reads them the same way a new
teammate would.
"""

from google.cloud import bigquery

# A single, module-level client is reused across calls rather than creating
# a new connection every time the agent invokes this tool - this matters
# once the agent is deployed and getting called repeatedly.
_client = bigquery.Client()

PROJECT_ID = "unfi-claims-agent"          # <-- replace with your project id
DATASET = "unfi_deductions"


def three_way_match(claim_id: str) -> dict:
    """
    Runs a three-way match for a supplier deduction claim.

    Compares the claim's linked purchase order, invoice, and receiving (POD)
    records to determine whether the deduction corresponds to a real
    quantity discrepancy, or whether the goods were fully received with no
    gap - which would mean the deduction is likely invalid.

    Args:
        claim_id: The deduction claim ID to check, e.g. "CLAIM-DEMO-001".

    Returns:
        A dictionary containing:
            claim_id, deduction_code, claim_amount, dispute_status,
            quantity_ordered, quantity_billed, quantity_received,
            condition_notes, billed_vs_received_gap, match_status,
            dispute_text
        If the claim_id does not exist, returns {"error": "..."} instead.
    """
    query = f"""
        SELECT
          c.claim_id,
          c.deduction_code,
          c.claim_amount,
          c.dispute_status,
          po.quantity_ordered,
          i.quantity_billed,
          r.quantity_received,
          r.condition_notes,
          c.dispute_text
        FROM `{PROJECT_ID}.{DATASET}.deduction_claims` AS c
        JOIN `{PROJECT_ID}.{DATASET}.invoices` AS i
          ON c.invoice_number = i.invoice_number
        JOIN `{PROJECT_ID}.{DATASET}.purchase_orders` AS po
          ON c.po_number = po.po_number
        JOIN `{PROJECT_ID}.{DATASET}.receiving` AS r
          ON c.po_number = r.po_number
        WHERE c.claim_id = @claim_id
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("claim_id", "STRING", claim_id),
        ]
    )

    rows = list(_client.query(query, job_config=job_config).result())

    if not rows:
        return {"error": f"No claim found with claim_id '{claim_id}'."}

    row = rows[0]

    # Explicitly cast BigQuery's NUMERIC/INTEGER types to plain Python
    # numbers - left as-is, these can behave like strings in comparisons.
    claim_amount = float(row["claim_amount"])
    quantity_ordered = int(row["quantity_ordered"])
    quantity_billed = int(row["quantity_billed"])
    quantity_received = int(row["quantity_received"])
    gap = quantity_billed - quantity_received

    # A lightweight, rules-based hint - NOT the final decision. The
    # classification sub-agent still reasons over this alongside the
    # deduction code policy and the supplier's dispute text.
    if gap > 0 and row["condition_notes"] in ("short", "damaged"):
        match_status = "discrepancy_confirmed"
    elif gap == 0 and row["condition_notes"] == "ok":
        match_status = "no_discrepancy_found"
    else:
        match_status = "needs_review"

    return {
        "claim_id": row["claim_id"],
        "deduction_code": row["deduction_code"],
        "claim_amount": claim_amount,
        "dispute_status": row["dispute_status"],
        "quantity_ordered": quantity_ordered,
        "quantity_billed": quantity_billed,
        "quantity_received": quantity_received,
        "condition_notes": row["condition_notes"],
        "billed_vs_received_gap": gap,
        "match_status": match_status,
        "dispute_text": row["dispute_text"],
    }


if __name__ == "__main__":
    # Quick manual test against your three planted demo cases, before
    # wiring this into the ADK agent at all.
    for test_id in ["CLAIM-DEMO-001", "CLAIM-DEMO-002", "CLAIM-DEMO-003", "CLAIM-DOES-NOT-EXIST"]:
        result = three_way_match(test_id)
        print(test_id, "->", result)