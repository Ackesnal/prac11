#!/usr/bin/env bash
# Instructor/admin preparation in a dedicated teaching project. Grants IAM roles.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# Normalise Windows CRLF before Bash expands dependent configuration values.
sed -i 's/\r$//' ./config.env
source ./config.env
: "${PROJECT_ID:?}" "${DEPLOYER_EMAIL:?}" "${RUNTIME_SA:?}" "${BUILD_SA:?}"
[[ "$PROJECT_ID" != REPLACE* && "$DEPLOYER_EMAIL" != REPLACE* ]] || { echo 'Edit config.env first.' >&2; exit 2; }
gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com aiplatform.googleapis.com iam.googleapis.com \
  --project "$PROJECT_ID"
for account in "$RUNTIME_SA" "$BUILD_SA"; do
  if ! gcloud iam service-accounts describe "$account" --project "$PROJECT_ID" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${account%%@*}" --project "$PROJECT_ID"
  fi
done
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$RUNTIME_SA" --role roles/aiplatform.user --condition=None
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:$BUILD_SA" --role roles/run.builder --condition=None
# run.admin also permits deploy.sh to keep service IAM private. This is a broad
# teaching-project convenience role, not a least-privilege production policy.
for role in roles/run.sourceDeveloper roles/run.admin roles/serviceusage.serviceUsageConsumer roles/aiplatform.user; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "user:$DEPLOYER_EMAIL" --role "$role" --condition=None
done
for account in "$RUNTIME_SA" "$BUILD_SA"; do
  gcloud iam service-accounts add-iam-policy-binding "$account" --project "$PROJECT_ID" \
    --member "user:$DEPLOYER_EMAIL" --role roles/iam.serviceAccountUser --condition=None
done
echo 'IAM propagation may take several minutes. Next: build_index.py, deploy.sh, grant_invoker.sh.'
