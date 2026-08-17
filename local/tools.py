"""
tools.py (local version)

Same four capabilities as the deployed agent, reimplemented against the
local SQLite file instead of BigQuery / Cloud SQL / Vertex AI Search:

    three_way_match(claim_id)   - was BigQuery, now SQLite
    lookup_deduction_policy(code_or_question) - was VertexAiSearchTool RAG
                                    over an HTML policy doc, now a direct
                                    lookup against the deduction_codes table
                                    (the same data the HTML doc was built
                                    from - just queried directly, since a
                                    12-row reference table doesn't need
                                    vector search)
    propose_resolution(claim_id) - unchanged logic, writes to SQLite
    get_case_history(claim_id)   - was Cloud SQL, now SQLite

Function signatures and return shapes are kept close to the original so
the agent instructions barely need to change.
"""

import json
from db import get_connection


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
        A dict with claim_id, deduction_code, claim_amount, dispute_status,
        quantity_ordered, quantity_billed, quantity_received,
        condition_notes, billed_vs_received_gap, match_status, dispute_text.
        {"error": "..."} if the claim_id does not exist.
    """
    conn = get_connection()
    row = conn.execute(
        """
        SELECT
          c.claim_id, c.deduction_code, c.claim_amount, c.dispute_status,
          po.quantity_ordered, i.quantity_billed, r.quantity_received,
          r.condition_notes, c.dispute_text
        FROM deduction_claims AS c
        JOIN invoices AS i ON c.invoice_number = i.invoice_number
        JOIN purchase_orders AS po ON c.po_number = po.po_number
        JOIN receiving AS r ON c.po_number = r.po_number
        WHERE c.claim_id = ?
        """,
        (claim_id,),
    ).fetchone()
    conn.close()

    if row is None:
        return {"error": f"No claim found with claim_id '{claim_id}'."}

    claim_amount = float(row["claim_amount"])
    quantity_ordered = int(row["quantity_ordered"])
    quantity_billed = int(row["quantity_billed"])
    quantity_received = int(row["quantity_received"])
    gap = quantity_billed - quantity_received

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


def lookup_deduction_policy(code: str) -> dict:
    """
    Looks up what a UNFI supplier deduction code means and how it should be
    evaluated, from the official Supplier Deduction Key reference table.
    This replaces the Vertex AI Search / RAG lookup used in the deployed
    version - the underlying content is the same deduction-code reference
    data, just queried directly instead of through semantic search.

    Args:
        code: The deduction code to look up, e.g. "SHORT-01" or "DAMAGE-02".
              Matching is case-insensitive.

    Returns:
        {"code", "description", "category", "typical_validity_notes"} if
        found, or {"error": "..."} if the code isn't in the reference table
        - never guess or invent a definition for an unknown code.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT code, description, category, typical_validity_notes "
        "FROM deduction_codes WHERE UPPER(code) = UPPER(?)",
        (code,),
    ).fetchone()
    conn.close()

    if row is None:
        return {"error": f"No deduction code '{code}' found in the Supplier Deduction Key."}

    return dict(row)


def log_resolution(
    claim_id: str,
    match_status: str,
    claim_amount: float,
    evidence: str,
    recommended_action: str,
) -> dict:
    """
    Writes a proposed resolution for a claim to the local case_history audit
    log, with analyst_decision defaulting to 'pending'. Does NOT approve or
    finalize anything - only records the agent's recommendation.
    """
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO case_history
            (claim_id, match_status, claim_amount, evidence, recommended_action)
        VALUES (?, ?, ?, ?, ?)
        """,
        (claim_id, match_status, claim_amount, evidence, recommended_action),
    )
    conn.commit()
    row_id = cursor.lastrowid
    created_at = conn.execute(
        "SELECT created_at FROM case_history WHERE id = ?", (row_id,)
    ).fetchone()["created_at"]
    conn.close()

    return {
        "case_history_id": row_id,
        "claim_id": claim_id,
        "analyst_decision": "pending",
        "created_at": created_at,
    }


def get_case_history(claim_id: str) -> dict:
    """
    Retrieves all past logged resolutions and analyst decisions for a given
    claim ID, most recent first. Use before proposing a new resolution, to
    check whether this claim already has history.

    Args:
        claim_id: The deduction claim ID to look up history for.

    Returns:
        {"claim_id": ..., "history": [...]} - empty list if never logged.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT id, match_status, claim_amount, recommended_action,
               analyst_decision, analyst_notes, created_at
        FROM case_history
        WHERE claim_id = ?
        ORDER BY created_at DESC
        """,
        (claim_id,),
    ).fetchall()
    conn.close()

    history = [
        {
            "case_history_id": r["id"],
            "match_status": r["match_status"],
            "claim_amount": float(r["claim_amount"]) if r["claim_amount"] is not None else None,
            "recommended_action": r["recommended_action"],
            "analyst_decision": r["analyst_decision"],
            "analyst_notes": r["analyst_notes"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    return {"claim_id": claim_id, "history": history}


def propose_resolution(claim_id: str) -> dict:
    """
    Proposes a resolution for a supplier deduction claim and logs it for
    human review. Runs the three-way match, applies simple rules-based
    reasoning about whether the discrepancy supports the deduction, and
    writes a pending draft to the audit log.

    This does NOT finalize, approve, or reverse anything on its own - it
    always returns a draft with status 'pending_human_approval'. A human
    analyst must review the evidence and make the final call.

    Args:
        claim_id: The deduction claim ID to propose a resolution for.

    Returns:
        The three-way match details plus recommended_action, status
        ("pending_human_approval"), and case_history_id. Or {"error": "..."}
        if the claim_id was not found.
    """
    match = three_way_match(claim_id)
    if "error" in match:
        return match

    status = match["match_status"]

    if status == "discrepancy_confirmed":
        recommended_action = (
            f"Uphold the ${match['claim_amount']:.2f} deduction. A confirmed "
            f"quantity discrepancy of {match['billed_vs_received_gap']} units "
            f"was found between billed and received quantities, consistent "
            f"with the deduction code {match['deduction_code']}."
        )
    elif status == "no_discrepancy_found":
        recommended_action = (
            f"Reverse the ${match['claim_amount']:.2f} deduction. Billed and "
            f"received quantities match exactly, with no supporting "
            f"discrepancy for deduction code {match['deduction_code']}."
        )
    else:  # needs_review
        recommended_action = (
            f"Escalate to a human analyst. The available data does not "
            f"clearly confirm or refute the ${match['claim_amount']:.2f} "
            f"deduction under code {match['deduction_code']} - additional "
            f"documentation (e.g. a damage inspection report or trade "
            f"agreement) is likely required."
        )

    log_result = log_resolution(
        claim_id=claim_id,
        match_status=status,
        claim_amount=match["claim_amount"],
        evidence=json.dumps(match),
        recommended_action=recommended_action,
    )

    return {
        **match,
        "recommended_action": recommended_action,
        "status": "pending_human_approval",
        "case_history_id": log_result["case_history_id"],
    }


if __name__ == "__main__":
    # Quick manual smoke test against the three planted demo cases.
    for test_id in ["CLAIM-DEMO-001", "CLAIM-DEMO-002", "CLAIM-DEMO-003", "CLAIM-DOES-NOT-EXIST"]:
        print(test_id, "->", three_way_match(test_id))

    print()
    print("SHORT-01 ->", lookup_deduction_policy("SHORT-01"))
    print("NOT-A-CODE ->", lookup_deduction_policy("NOT-A-CODE"))

    print()
    print("propose_resolution(CLAIM-DEMO-002) ->", propose_resolution("CLAIM-DEMO-002"))
    print("get_case_history(CLAIM-DEMO-002) ->", get_case_history("CLAIM-DEMO-002"))
