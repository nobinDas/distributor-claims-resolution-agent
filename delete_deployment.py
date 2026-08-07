"""
delete_deployment.py

Deletes a deployed Agent Runtime resource. Run this when you're done
testing for the day - a deployed agent engine bills continuously while it
exists, similar to Cloud SQL.

Usage:
    python delete_deployment.py \
        --project unfi-claims-agent \
        --location us-central1 \
        --resource-name projects/.../locations/.../reasoningEngines/RESOURCE_ID
"""

import argparse
import vertexai


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--resource-name", required=True)
    args = parser.parse_args()

    client = vertexai.Client(project=args.project, location=args.location)

    confirm = input(f"Delete {args.resource_name}? This cannot be undone. [y/N]: ")
    if confirm.strip().lower() != "y":
        print("Cancelled.")
        return

    client.agent_engines.delete(name=args.resource_name, force=True)
    print("Deleted.")


if __name__ == "__main__":
    main()