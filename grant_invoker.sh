#!/usr/bin/env bash
# Run by an administrator with permission to change service IAM, after deployment.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
source ./config.env
: "${INVOKER_EMAIL:?}"
gcloud run services add-iam-policy-binding "$SERVICE_NAME" --project "$PROJECT_ID" \
  --region "$RUN_REGION" --member "user:$INVOKER_EMAIL" --role roles/run.invoker
gcloud run services get-iam-policy "$SERVICE_NAME" --project "$PROJECT_ID" --region "$RUN_REGION"
