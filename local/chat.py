"""
chat.py

Terminal chat loop for the local UNFI Claims Resolution Agent - the
local-machine replacement for chatting with it through Gemini Enterprise.

Usage:
    python chat.py

Try:
    Look up CLAIM-DEMO-001
    What does deduction code DAMAGE-02 mean?
    Propose a resolution for CLAIM-DEMO-003
    Has CLAIM-DEMO-002 been looked at before?
"""

import os
import sys
from pathlib import Path

# Load .env if python-dotenv is available; harmless if the file is absent.
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

from db import DB_PATH, create_schema
from agent import build_chat, send


def main():
    if not DB_PATH.exists():
        print(f"No local database found at {DB_PATH}.")
        print("Run this first:  python generate_synthetic_data.py")
        sys.exit(1)

    try:
        chat = build_chat()
    except RuntimeError as e:
        print(f"Setup error: {e}")
        sys.exit(1)

    print("UNFI Supplier Deduction & Claims Resolution Agent (local)")
    print("Type a message, or 'exit' / 'quit' to stop.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye.")
            break

        try:
            reply = send(chat, user_input)
        except Exception as e:
            print(f"[error] {e}\n")
            continue

        print(f"\nAgent: {reply}\n")


if __name__ == "__main__":
    main()
