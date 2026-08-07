"""
test_deployed_agent.py

Sends real test queries to your deployed Agent Runtime endpoint, to confirm
the deployment actually works end to end (not just that deployment
succeeded without erroring).

Usage:
    python test_deployed_agent.py \
        --project unfi-claims-agent \
        --location us-central1 \
        --resource-name projects/.../locations/.../reasoningEngines/RESOURCE_ID
"""

import argparse
import asyncio
import vertexai


async def run_test_queries(client, resource_name):
    agent_engine = client.agent_engines.get(name=resource_name)

    test_queries = [
        "Can you check claim CLAIM-DEMO-001?",
        "What does deduction code DAMAGE-02 mean?",
        "Propose a resolution for CLAIM-DEMO-003.",
    ]

    session = await agent_engine.async_create_session(user_id="test-user")

    for query in test_queries:
        print(f"\n{'=' * 60}")
        print(f"QUERY: {query}")
        print("=" * 60)
        async for event in agent_engine.async_stream_query(
            user_id="test-user",
            session_id=session["id"],
            message=query,
        ):
            print(event)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--resource-name", required=True,
                         help="Full resource name printed by deploy.py")
    args = parser.parse_args()

    client = vertexai.Client(project=args.project, location=args.location)

    asyncio.run(run_test_queries(client, args.resource_name))


if __name__ == "__main__":
    main()