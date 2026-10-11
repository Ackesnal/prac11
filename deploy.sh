#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
source ./config.env
: "${PROJECT_ID:?}" "${RUN_REGION:?}" "${MODEL_ID:?}" "${RUNTIME_SA:?}" "${BUILD_SA:?}" "${SERVICE_NAME:?}"
[[ "$PROJECT_ID" != REPLACE* ]] || { echo 'Edit config.env first.' >&2; exit 2; }
python -c 'from app import services; p,r=services(); print("Validated index:",len(r.chunks),"chunks")'
gcloud run deploy "$SERVICE_NAME" --project "$PROJECT_ID" --region "$RUN_REGION" \
  --source . --service-account "$RUNTIME_SA" \
  --build-service-account "projects/$PROJECT_ID/serviceAccounts/$BUILD_SA" \
  --no-allow-unauthenticated --invoker-iam-check \
  --concurrency 4 --max-instances 2 --min-instances 0 --timeout 180 \
  --memory 512Mi --cpu 1 \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID,MODEL_LOCATION=$MODEL_LOCATION,MODEL_ID=$MODEL_ID,EMBEDDING_MODEL=$EMBEDDING_MODEL,EMBEDDING_LOCATION=$EMBEDDING_LOCATION,EMBEDDING_DIM=$EMBEDDING_DIM,TOP_K=$TOP_K,MIN_SCORE=$MIN_SCORE"
gcloud run services describe "$SERVICE_NAME" --project "$PROJECT_ID" --region "$RUN_REGION" \
  --format='yaml(status.url,status.latestReadyRevisionName,spec.template.spec.serviceAccountName)'
