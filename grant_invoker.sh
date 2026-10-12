#!/usr/bin/env bash
# Run by an administrator with permission to change service IAM, after deployment.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# Normalise Windows CRLF before Bash expands dependent configuration values.
sed -i 's/\r$//' ./config.env
source ./config.env
: "${INVOKER_EMAIL:?}"
gcloud run services add-iam-policy-binding "$SERVICE_NAME" --project "$PROJECT_ID" \
  --region "$RUN_REGION" --member "user:$INVOKER_EMAIL" --role roles/run.invoker
gcloud run services get-iam-policy "$SERVICE_NAME" --project "$PROJECT_ID" --region "$RUN_REGION"
echo 'Next (in your current terminal): source ./config.env'
echo 'A bash script cannot export its configuration back to the parent terminal.'
