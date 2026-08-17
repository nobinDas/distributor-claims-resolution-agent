#!/bin/bash
# setup_cloud_sql.sh
#
# Creates the Cloud SQL Postgres instance, database, and application user
# used for the claims agent's case history / audit log.
#
# Edit the variables below before running, especially DB_PASSWORD.
# Usage:
#   chmod +x setup_cloud_sql.sh
#   ./setup_cloud_sql.sh

set -e  # stop immediately if any command fails

PROJECT_ID="unfi-claims-agent"      # <-- your project ID
INSTANCE="claims-db"
REGION="us-central1"
DB_NAME="claims_db"
DB_USER="claims_app"
DB_PASSWORD="xQ7mK9!vL2#nR8p"   # <-- change this before running

echo "Creating Cloud SQL instance (smallest tier)..."
gcloud sql instances create "$INSTANCE" \
  --project="$PROJECT_ID" \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region="$REGION" \
  --storage-size=10GB \
  --storage-auto-increase

echo "Creating database..."
gcloud sql databases create "$DB_NAME" \
  --project="$PROJECT_ID" \
  --instance="$INSTANCE"

echo "Creating application user..."
gcloud sql users create "$DB_USER" \
  --project="$PROJECT_ID" \
  --instance="$INSTANCE" \
  --password="$DB_PASSWORD"

echo ""
echo "Done. Instance connection name (needed by the Python connector):"
gcloud sql instances describe "$INSTANCE" \
  --project="$PROJECT_ID" \
  --format="value(connectionName)"

echo ""
echo "IMPORTANT cost habit: stop this instance between work sessions with:"
echo "  gcloud sql instances patch $INSTANCE --project=$PROJECT_ID --activation-policy=NEVER"
echo "And restart it before your next session with:"
echo "  gcloud sql instances patch $INSTANCE --project=$PROJECT_ID --activation-policy=ALWAYS"