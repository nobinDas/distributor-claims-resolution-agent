"""
resolution_tool.py

propose_resolution(claim_id) - the tool that ties everything together:
runs the three-way match, drafts a recommended action, logs it to the
case_history audit log as a PENDING draft, and returns it for human
review. It never marks anything as approved - only a human analyst
(via the triage queue, built in Phase 6) can do that.
"""

import json
from .tools import three_way_match
from .case_memory_tools import log_resolution


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
        A dictionary with the three-way match details plus:
            recommended_action: a short, human-readable recommendation
            status: always "pending_human_approval"
            case_history_id: the audit log row this was recorded under
        Or {"error": "..."} if the claim_id was not found.
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