#!/usr/bin/env bash
# Set RUNPOD_ENDPOINT_ID on Railway after RunPod endpoint is created.
# Usage: bash set_railway_endpoint.sh <ENDPOINT_ID>
set -euo pipefail

ENDPOINT_ID="${1:?Usage: $0 <RUNPOD_ENDPOINT_ID>}"

railway variable set "RUNPOD_ENDPOINT_ID=$ENDPOINT_ID" \
  --project 655be345-1299-4b65-8f10-102dbff17ed8 \
  --environment production \
  --service api

echo "RUNPOD_ENDPOINT_ID=$ENDPOINT_ID set on Railway API service."
echo "API will redeploy — inference will switch to real mode."
