#!/usr/bin/env bash
# Deploys Insaan to Snowflake: SQL objects (procedures/views) first, then the Streamlit app.
#
# Usage:
#   ./deploy.sh                      # uses your default snow CLI connection
#   ./deploy.sh -c my_connection     # uses a named connection
#   ./deploy.sh -x                   # temporary connection from SNOWFLAKE_* env vars (CI)
#
# Any arguments are passed straight through to every `snow` command.
# Assumes HEALTHCARE_DW, the INSAAN schema, INSAAN_AGENT and the semantic view already exist.
set -euo pipefail

cd "$(dirname "$0")"

SQL_FILES=(
  sql/book_appointment.sql
  sql/stage4_self_serve.sql
  sql/stage6_sentiment.sql
)

for f in "${SQL_FILES[@]}"; do
  echo "==> Running $f"
  snow sql -f "$f" "$@"
done

echo "==> Deploying Streamlit app"
snow streamlit deploy insaan --replace "$@"

echo "==> Done"
