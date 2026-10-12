#!/usr/bin/env bash
# Deletes only the selected demo service. Shared IAM, images and build storage remain.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# Normalise Windows CRLF before Bash expands dependent configuration values.
sed -i 's/\r$//' ./config.env
source ./config.env
: "${PROJECT_ID:?}" "${RUN_REGION:?}" "${SERVICE_NAME:?}"
gcloud run services delete "$SERVICE_NAME" --project "$PROJECT_ID" --region "$RUN_REGION"
echo 'Review the cloud-run-source-deploy Artifact Registry repository and Cloud Build storage with your tutor.'
echo 'Do not delete a shared repository, bucket, service account or project.'
