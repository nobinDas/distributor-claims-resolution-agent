"""
create_case_history_table.py

Creates the case_history table in the Cloud SQL Postgres instance. This
table is the agent's audit log: every proposed resolution gets written
here, along with whether a human analyst later approved, edited, or
rejected it.

Prerequisites:
    pip install "cloud-sql-python-connector[pg8000]"
    Run setup_cloud_sql.sh first to create the instance/database/user.

Usage:
    python create_case_history_table.py \
        --project YOUR_PROJECT_ID \
        --region us-central1 \
        --instance claims-db \
        --database claims_db \
        --db-user claims_app \
        --db-password YOUR_DB_PASSWORD
"""

import argparse
from google.cloud.sql.connector import Connector
import pg8000


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS case_history (
    id                 SERIAL PRIMARY KEY,
    claim_id           VARCHAR(50)   NOT NULL,
    match_status       VARCHAR(50),
    claim_amount       NUMERIC(12,2),
    evidence           TEXT,
    recommended_action TEXT,
    analyst_decision   VARCHAR(20)   NOT NULL DEFAULT 'pending',
    analyst_notes      TEXT,
    created_at         TIMESTAMP     NOT NULL DEFAULT now()
);
"""

CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_case_history_claim_id
    ON case_history (claim_id);
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--instance", default="claims-db")
    parser.add_argument("--database", default="claims_db")
    parser.add_argument("--db-user", default="claims_app")
    parser.add_argument("--db-password", required=True)
    args = parser.parse_args()

    instance_connection_name = f"{args.project}:{args.region}:{args.instance}"

    connector = Connector()

    def getconn():
        return connector.connect(
            instance_connection_name,
            "pg8000",
            user=args.db_user,
            password=args.db_password,
            db=args.database,
        )

    conn = getconn()
    cursor = conn.cursor()
    cursor.execute(CREATE_TABLE_SQL)
    cursor.execute(CREATE_INDEX_SQL)
    conn.commit()
    cursor.close()
    conn.close()
    connector.close()

    print("Done. case_history table is ready in", instance_connection_name)


if __name__ == "__main__":
    main()