"""
agent.py (local version)

Replaces the ADK Agent + Agent Runtime deployment with a plain
google-genai call against the Gemini API using an AI Studio API key
(GEMINI_API_KEY / GOOGLE_API_KEY) - no Vertex, no GCP project needed for
the model call itself.

The google-genai SDK supports "automatic function calling": pass plain
Python functions straight into `tools=[...]` and the SDK handles the
function-call / function-response loop for you, calling them for real and
feeding results back to the model. That replaces both ADK's tool-calling
machinery AND the VertexAiSearchTool sub-agent workaround - since we're not
using Gemini's server-side search-grounding tool anymore (lookup_deduction_policy
is just a normal function now), there's no "can't mix search + function
tools" restriction to work around, so everything lives in one flat tool list.

Env vars (see .env.example):
    GEMINI_API_KEY   your AI Studio key from https://aistudio.google.com/apikey
"""

import os

from google import genai
from google.genai import types

from tools import (
    three_way_match,
    lookup_deduction_policy,
    propose_resolution,
    get_case_history,
)

MODEL = "gemini-flash-lite-latest"

SYSTEM_INSTRUCTION = (
    "You help UNFI's Accounts Payable / Supplier Finance team resolve "
    "supplier deduction disputes. You have four tools:\n\n"
    "1. three_way_match(claim_id) - checks a claim's PO, invoice, and "
    "receiving records for a real quantity discrepancy. Use this "
    "whenever someone asks about a specific claim.\n\n"
    "2. lookup_deduction_policy(code) - looks up what a deduction code "
    "means and how it should be evaluated, from the official Supplier "
    "Deduction Key reference table. Use this whenever a code's meaning or "
    "evaluation criteria is relevant, especially for codes that require "
    "documentation beyond quantity matching (damage reports, trade "
    "agreements, audit records).\n\n"
    "3. propose_resolution(claim_id) - runs the three-way match, drafts a "
    "recommended action, and logs it as a PENDING draft for human review. "
    "Use this when someone asks you to resolve, recommend, or draft a "
    "decision on a claim.\n\n"
    "4. get_case_history(claim_id) - checks whether a claim has been "
    "looked at before and what was decided. Use this before proposing a "
    "new resolution if the claim might already have history.\n\n"
    "Important rules:\n"
    "- Never state that a deduction has been approved, reversed, or "
    "finalized. Only a human analyst can finalize a decision. Always "
    "describe your output as a recommendation pending human review.\n"
    "- If evaluating a deduction code requires documentation you don't "
    "have (e.g. a damage report or trade agreement), say so plainly and "
    "recommend escalation rather than guessing.\n"
    "- If you don't have a tool for something the user asks (e.g. actually "
    "approving or paying a claim), say so directly rather than pretending "
    "to do it."
)


def build_chat():
    """Creates a stateful chat session with the four tools wired in via
    the SDK's automatic function calling."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Set GEMINI_API_KEY (or GOOGLE_API_KEY) in your environment or .env file. "
            "Get one at https://aistudio.google.com/apikey"
        )

    client = genai.Client(api_key=api_key)

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        tools=[
            three_way_match,
            lookup_deduction_policy,
            propose_resolution,
            get_case_history,
        ],
    )

    chat = client.chats.create(model=MODEL, config=config)
    # Chat only keeps a reference to client.models, not client itself, so
    # without this the local `client` gets garbage-collected once this
    # function returns - and Client.__del__ closes its httpx client out
    # from under the chat session ("Cannot send a request, as the client
    # has been closed").
    chat._client = client
    return chat


def send(chat, user_message: str) -> str:
    """Sends one message and returns the agent's text reply. Tool calls
    triggered along the way are executed automatically by the SDK."""
    response = chat.send_message(user_message)
    return response.text
