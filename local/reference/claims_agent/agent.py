"""
agent.py

Root agent definition for the UNFI Supplier Deduction & Claims Resolution
Agent. Place this file inside claims_agent/, alongside tools.py,
case_memory_tools.py, and resolution_tool.py.

IMPORTANT: Gemini does not allow mixing custom function tools with a
search/retrieval tool (like VertexAiSearchTool) in the same model call.
To work around this, the search tool lives on its own small sub-agent,
which is then wrapped as an AgentTool - from the root agent's point of
view, it's just another callable tool, same as three_way_match.
"""

from google.adk.agents import Agent
from google.adk.tools import VertexAiSearchTool
from google.adk.tools.agent_tool import AgentTool

from .tools import three_way_match
from .resolution_tool import propose_resolution
from .case_memory_tools import get_case_history

# --- Vertex AI Search grounding -------------------------------------------
# The full Data Store ID from the console, including the auto-appended
# numeric suffix.
DEDUCTION_KEY_DATASTORE_ID = (
    "projects/60936267443/locations/global/collections/default_collection/"
    "dataStores/deduction-key-datastore_1785875969416"
)

deduction_key_search = VertexAiSearchTool(
    data_store_id=DEDUCTION_KEY_DATASTORE_ID,
)

# --- Sub-agent: policy/deduction-code lookup -------------------------------
# This agent's ONLY tool is the search tool, which satisfies Gemini's
# "search tools can't be mixed with function tools" rule at this level.
policy_lookup_agent = Agent(
    model="gemini-2.5-flash",
    name="policy_lookup_agent",
    instruction=(
        "You answer questions about what UNFI's supplier deduction codes "
        "mean and how they should be evaluated, using only the Supplier "
        "Deduction Key document you have access to. If the document does "
        "not contain a code the user asks about, say plainly that you "
        "don't have information on that code - never guess or invent a "
        "plausible-sounding definition."
    ),
    tools=[deduction_key_search],
)

# Wrap the sub-agent as a regular tool the root agent can call. This is a
# normal function-tool from Gemini's perspective, so it can safely sit
# alongside three_way_match, propose_resolution, and get_case_history.
policy_lookup_tool = AgentTool(agent=policy_lookup_agent)

# --- Root agent -------------------------------------------------------------
root_agent = Agent(
    model="gemini-2.5-flash",
    name="claims_orchestrator",
    instruction=(
        "You help UNFI's Accounts Payable / Supplier Finance team resolve "
        "supplier deduction disputes. You have four tools:\n\n"
        "1. three_way_match(claim_id) - checks a claim's PO, invoice, and "
        "receiving records for a real quantity discrepancy. Use this "
        "whenever someone asks about a specific claim.\n\n"
        "2. policy_lookup_agent - looks up what a deduction code means and "
        "how it should be evaluated, from the official Supplier Deduction "
        "Key document. Use this whenever a code's meaning or evaluation "
        "criteria is relevant, especially for codes that require "
        "documentation beyond quantity matching (damage reports, trade "
        "agreements, audit records).\n\n"
        "3. propose_resolution(claim_id) - runs the three-way match, drafts "
        "a recommended action, and logs it as a PENDING draft for human "
        "review. Use this when someone asks you to resolve, recommend, or "
        "draft a decision on a claim.\n\n"
        "4. get_case_history(claim_id) - checks whether a claim has been "
        "looked at before and what was decided. Use this before proposing "
        "a new resolution if the claim might already have history.\n\n"
        "Important rules:\n"
        "- Never state that a deduction has been approved, reversed, or "
        "finalized. Only a human analyst can finalize a decision. Always "
        "describe your output as a recommendation pending human review.\n"
        "- If evaluating a deduction code requires documentation you don't "
        "have (e.g. a damage report or trade agreement), say so plainly and "
        "recommend escalation rather than guessing.\n"
        "- If you don't have a tool for something the user asks (e.g. "
        "actually approving or paying a claim), say so directly rather "
        "than pretending to do it."
    ),
    tools=[
        three_way_match,
        policy_lookup_tool,
        propose_resolution,
        get_case_history,
    ],
)