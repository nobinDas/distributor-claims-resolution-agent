"""
case_memory_tools.py

Cloud SQL-backed tool functions for the claims agent: writing a proposed
resolution to the audit log (log_resolution) and retrieving past history
for a claim (get_case_history). Both are plain Python functions passed
into the ADK Agent's tools=[] list, same pattern as three_way_match.

Configuration is read from environment variables so credentials never
live in code. Set these in claims_agent/.env:

    CLOUDSQL_INSTANCE_CONNECTION_NAME=your-project:us-central1:claims-db
    CLOUDSQL_DATABASE=claims_db
    CLOUDSQL_DB_USER=claims_app
    CLOUDSQL_DB_PASSWORD=your-db-password

Prerequisites:
    pip install "cloud-sql-python-connector[pg8000]"
"""

import os
import json
from google.cloud.sql.connector import Connector

_connector = Connector()  # reused across calls, same pattern as the BigQuery client


def _get_connection():
    instance_connection_name = os.environ["CLOUDSQL_INSTANCE_CONNECTION_NAME"]
    return _connector.connect(
        instance_connection_name,
        "pg8000",
        user=os.environ["CLOUDSQL_DB_USER"],
        password=os.environ["CLOUDSQL_DB_PASSWORD"],
        db=os.environ["CLOUDSQL_DATABASE"],
    )


def log_resolution(
    claim_id: str,
    match_status: str,
    claim_amount: float,
    evidence: str,
    recommended_action: str,
) -> dict:
    """
    Writes a proposed resolution for a claim to the case_history audit log,
    with analyst_decision defaulting to 'pending'. This does NOT approve or
    finalize anything - it only records the agent's recommendation for a
    human analyst to review later.

    Args:
        claim_id: The deduction claim ID this resolution is for.
        match_status: The three-way match result, e.g. "discrepancy_confirmed".
        claim_amount: The dollar amount of the claim.
        evidence: A JSON string capturing the supporting data used.
        recommended_action: A short, human-readable recommendation.

    Returns:
        A dictionary with the new case_history row's id and status.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO case_history
            (claim_id, match_status, claim_amount, evidence, recommended_action)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, created_at;
        """,
        (claim_id, match_status, claim_amount, evidence, recommended_action),
    )
    row = cursor.fetchone()
    conn.commit()
    cursor.close()
    conn.close()

    return {
        "case_history_id": row[0],
        "claim_id": claim_id,
        "analyst_decision": "pending",
        "created_at": str(row[1]),
    }


def get_case_history(claim_id: str) -> dict:
    """
    Retrieves all past logged resolutions and analyst decisions for a
    given claim ID, most recent first. Use this to check whether a claim
    has been looked at before, or what a human analyst previously decided.

    Args:
        claim_id: The deduction claim ID to look up history for.

    Returns:
        A dictionary with a "history" list of past entries (empty list if
        this claim has never been logged before).
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, match_status, claim_amount, recommended_action,
               analyst_decision, analyst_notes, created_at
        FROM case_history
        WHERE claim_id = %s
        ORDER BY created_at DESC;
        """,
        (claim_id,),
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    history = [
        {
            "case_history_id": r[0],
            "match_status": r[1],
            "claim_amount": float(r[2]) if r[2] is not None else None,
            "recommended_action": r[3],
            "analyst_decision": r[4],
            "analyst_notes": r[5],
            "created_at": str(r[6]),
        }
        for r in rows
    ]

    return {"claim_id": claim_id, "history": history}


if __name__ == "__main__":
    # Quick manual test - requires the env vars above to be set first, e.g.:
    #   export CLOUDSQL_INSTANCE_CONNECTION_NAME=your-project:us-central1:claims-db
    #   export CLOUDSQL_DATABASE=claims_db
    #   export CLOUDSQL_DB_USER=claims_app
    #   export CLOUDSQL_DB_PASSWORD=your-db-password
    result = log_resolution(
        claim_id="CLAIM-DEMO-002",
        match_status="no_discrepancy_found",
        claim_amount=105.0,
        evidence=json.dumps({"gap": 0, "condition_notes": "ok"}),
        recommended_action="Reverse deduction - no supporting discrepancy found.",
    )
    print("Logged:", result)

    history = get_case_history("CLAIM-DEMO-002")
    print("History:", history)