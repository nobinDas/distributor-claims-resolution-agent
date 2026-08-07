import argparse
import vertexai
from vertexai.agent_engines import AdkApp

from claims_agent.agent import root_agent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--location", default="us-central1")
    parser.add_argument("--staging-bucket", required=True)
    parser.add_argument("--cloudsql-instance", required=True)
    parser.add_argument("--cloudsql-database", default="claims_db")
    parser.add_argument("--cloudsql-user", default="claims_app")
    parser.add_argument("--cloudsql-password", required=True)
    parser.add_argument("--service-account", required=True)
    args = parser.parse_args()

    client = vertexai.Client(project=args.project, location=args.location)

    adk_app = AdkApp(agent=root_agent)

    env_vars = {
        "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
        "CLOUDSQL_INSTANCE_CONNECTION_NAME": args.cloudsql_instance,
        "CLOUDSQL_DATABASE": args.cloudsql_database,
        "CLOUDSQL_DB_USER": args.cloudsql_user,
        "CLOUDSQL_DB_PASSWORD": args.cloudsql_password,
    }

    print("Deploying... this typically takes several minutes.")

    agent_engine = client.agent_engines.create(
        agent=adk_app,
        config={
            "staging_bucket": args.staging_bucket,
            "display_name": "unfi-claims-orchestrator",
            "extra_packages": ["claims_agent"],
            "service_account": args.service_account,
            "requirements": [
                "google-cloud-aiplatform[agent_engines,adk]",
                "google-adk",
                "google-cloud-bigquery",
                "google-cloud-discoveryengine",
                "cloud-sql-python-connector[pg8000]",
                "pg8000",
                "cloudpickle",
                "pydantic",
            ],
            "env_vars": env_vars,
        },
    )

    print("\nDeployed successfully.")
    print("Resource name (save this - you'll need it to query or delete it):")
    print(agent_engine.api_resource.name)


if __name__ == "__main__":
    main()
