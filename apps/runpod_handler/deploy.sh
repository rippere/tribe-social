#!/usr/bin/env bash
# Build and deploy tribe-v2 RunPod Serverless endpoint.
# Run this after: docker login
#
# Usage: bash deploy.sh [DOCKERHUB_USER]
#   Default DOCKERHUB_USER = rippere
#
# What it does:
#   1. Build the CUDA Docker image
#   2. Push to DockerHub
#   3. Create RunPod template + endpoint via GraphQL API
#   4. Print the RUNPOD_ENDPOINT_ID to set on Railway

set -euo pipefail

DOCKERHUB_USER="${1:-rippere}"
IMAGE_TAG="${DOCKERHUB_USER}/tribe-v2-inference:latest"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Secrets live in an untracked, gitignored .deploy.env (or your shell env) — never committed.
[ -f "$SCRIPT_DIR/.deploy.env" ] && source "$SCRIPT_DIR/.deploy.env"
HF_TOKEN="${HF_TOKEN:?set HF_TOKEN in apps/runpod_handler/.deploy.env or export it}"
RUNPOD_API_KEY="${RUNPOD_API_KEY:?set RUNPOD_API_KEY in apps/runpod_handler/.deploy.env or export it}"

echo "==> Building image: $IMAGE_TAG"
docker build \
  --build-arg HF_TOKEN="$HF_TOKEN" \
  -t "$IMAGE_TAG" \
  "$SCRIPT_DIR"

echo "==> Pushing to DockerHub..."
docker push "$IMAGE_TAG"

echo "==> Creating RunPod template..."
TEMPLATE_RESPONSE=$(curl -s -X POST https://api.runpod.io/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d "{
    \"query\": \"mutation { saveTemplate(input: { name: \\\"tribe-v2-inference\\\", imageName: \\\"$IMAGE_TAG\\\", dockerArgs: \\\"\\\", isServerless: true, containerDiskInGb: 20, volumeInGb: 0, env: [{ key: \\\"HF_TOKEN\\\", value: \\\"$HF_TOKEN\\\" }] }) { id name imageName } }\"
  }")

echo "Template response: $TEMPLATE_RESPONSE"
TEMPLATE_ID=$(echo "$TEMPLATE_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['saveTemplate']['id'])")
echo "==> Template ID: $TEMPLATE_ID"

echo "==> Creating RunPod Serverless endpoint..."
ENDPOINT_RESPONSE=$(curl -s -X POST https://api.runpod.io/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d "{
    \"query\": \"mutation { saveEndpoint(input: { name: \\\"tribe-v2-inference\\\", templateId: \\\"$TEMPLATE_ID\\\", workersMin: 0, workersMax: 3, idleTimeout: 60, gpuIds: \\\"AMPERE_16\\\" }) { id name } }\"
  }")

echo "Endpoint response: $ENDPOINT_RESPONSE"
ENDPOINT_ID=$(echo "$ENDPOINT_RESPONSE" | python3 -c "import json,sys; print(json.load(sys.stdin)['data']['saveEndpoint']['id'])")

echo ""
echo "====================================="
echo "SUCCESS — RunPod Endpoint deployed!"
echo "====================================="
echo "ENDPOINT_ID: $ENDPOINT_ID"
echo ""
echo "Now set this on Railway API service:"
echo "  railway variable set RUNPOD_ENDPOINT_ID=$ENDPOINT_ID \\"
echo "    --project 655be345-1299-4b65-8f10-102dbff17ed8 \\"
echo "    --environment production --service api"
echo ""
echo "Or run: bash $(dirname "$0")/set_railway_endpoint.sh $ENDPOINT_ID"
