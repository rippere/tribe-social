#!/usr/bin/env bash
# Create RunPod Serverless endpoint.
# Run this AFTER funding your RunPod account (minimum $0.01 balance required).
#
# What it does:
#   1. Creates a serverless template (isServerless: true) from the Docker image
#   2. Creates the endpoint from that template (workersMax=0 = starts disabled)
#   3. Prints the ENDPOINT_ID to set on Railway
#
# Usage: bash create_endpoint.sh

set -euo pipefail

IMAGE_TAG="rippere/tribe-v2-inference:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Secrets live in an untracked, gitignored .deploy.env (or your shell env) — never committed.
[ -f "$SCRIPT_DIR/.deploy.env" ] && source "$SCRIPT_DIR/.deploy.env"
HF_TOKEN="${HF_TOKEN:?set HF_TOKEN in apps/runpod_handler/.deploy.env or export it}"
RUNPOD_API_KEY="${RUNPOD_API_KEY:?set RUNPOD_API_KEY in apps/runpod_handler/.deploy.env or export it}"

echo "==> Creating serverless template from $IMAGE_TAG..."
TEMPLATE_RESPONSE=$(curl -s -X POST https://api.runpod.io/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d "{
    \"query\": \"mutation { saveTemplate(input: { name: \\\"tribe-v2-serverless\\\", imageName: \\\"$IMAGE_TAG\\\", dockerArgs: \\\"\\\", isServerless: true, containerDiskInGb: 20, volumeInGb: 0, env: [{ key: \\\"HF_TOKEN\\\", value: \\\"$HF_TOKEN\\\" }] }) { id name } }\"
  }")

TEMPLATE_ID=$(echo "$TEMPLATE_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['saveTemplate']['id'])")
echo "==> Template ID: $TEMPLATE_ID"

echo "==> Creating serverless endpoint..."
ENDPOINT_RESPONSE=$(curl -s -X POST https://api.runpod.io/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d "{
    \"query\": \"mutation { saveEndpoint(input: { name: \\\"tribe-v2-inference\\\", templateId: \\\"$TEMPLATE_ID\\\", workersMin: 0, workersMax: 0, idleTimeout: 5, gpuIds: \\\"AMPERE_16\\\" }) { id name } }\"
  }")

ENDPOINT_ID=$(echo "$ENDPOINT_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['saveEndpoint']['id'])")

echo ""
echo "====================================="
echo "SUCCESS — RunPod Endpoint deployed!"
echo "====================================="
echo "Template ID:  $TEMPLATE_ID"
echo "Endpoint ID:  $ENDPOINT_ID"
echo ""
echo "Now activate real inference mode on Railway:"
echo "  bash $(dirname "$0")/set_railway_endpoint.sh $ENDPOINT_ID"
