"""
RunPod Serverless async client — Phase 3.
No SSH, no paramiko, no GraphQL. Pure REST + GraphQL for endpoint control.

Cost-control pattern:
  enable_endpoint()  → set workersMax=3 before submitting a job
  disable_endpoint() → set workersMax=0 immediately after result retrieved
This ensures workers spin down as soon as the job is done rather than waiting
for idleTimeout, preventing runaway charges.
"""
import asyncio
import base64
import os
from typing import Any

import httpx

RUNPOD_API_KEY     = os.getenv("RUNPOD_API_KEY", "")
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID", "")
_BASE      = "https://api.runpod.ai/v2"
_GQL_URL   = "https://api.runpod.io/graphql"
_MAX_WORKERS = 3

POLL_INTERVAL_S = 5
POLL_TIMEOUT_S  = 600


def _headers() -> dict:
    return {"Authorization": f"Bearer {RUNPOD_API_KEY}", "Content-Type": "application/json"}


ENDPOINT_NAME = os.getenv("RUNPOD_ENDPOINT_NAME", "tribe-v2-inference")
ENDPOINT_GPU_IDS = os.getenv("RUNPOD_GPU_IDS", "AMPERE_16")


async def _set_workers_max(n: int) -> None:
    """Enable (n>0) or disable (n=0) the endpoint via GraphQL."""
    if not RUNPOD_API_KEY or not RUNPOD_ENDPOINT_ID:
        return
    # name and gpuIds are required by RunPod's EndpointInput even for updates
    mutation = (
        "mutation { saveEndpoint(input: {"
        f' id: "{RUNPOD_ENDPOINT_ID}",'
        f' name: "{ENDPOINT_NAME}",'
        f' gpuIds: "{ENDPOINT_GPU_IDS}",'
        f" workersMin: 0, workersMax: {n}"
        " }) { id workersMax } }"
    )
    async with httpx.AsyncClient(timeout=15) as client:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = await asyncio.wait_for(
                    client.post(
                        _GQL_URL,
                        json={"query": mutation},
                        headers=_headers(),
                    ),
                    timeout=15,
                )
                data = resp.json()
                if "errors" in data:
                    raise RuntimeError(f"RunPod saveEndpoint failed: {data['errors']}")
                return
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc


async def enable_endpoint() -> None:
    await _set_workers_max(_MAX_WORKERS)


async def disable_endpoint() -> None:
    await _set_workers_max(0)


async def submit(video_bytes: bytes, filename: str) -> str:
    payload = base64.b64encode(video_bytes).decode()
    url = f"{_BASE}/{RUNPOD_ENDPOINT_ID}/run"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            json={"input": {"video_b64": payload, "filename": filename}},
            headers=_headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        if "id" not in data:
            raise RuntimeError(f"RunPod submit returned no job id: {data}")
        return data["id"]


async def check_status(runpod_job_id: str) -> dict[str, Any]:
    """Single status check — returns raw RunPod response dict."""
    url = f"{_BASE}/{RUNPOD_ENDPOINT_ID}/status/{runpod_job_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=_headers())
        resp.raise_for_status()
        data = resp.json()
        if "status" not in data:
            raise RuntimeError(f"RunPod check_status returned no 'status' field: {data}")
        return data


async def poll(runpod_job_id: str) -> dict[str, Any]:
    """Poll until terminal state. Returns normalised result dict."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + POLL_TIMEOUT_S
    while True:
        if loop.time() > deadline:
            raise TimeoutError(f"RunPod job {runpod_job_id} timed out after {POLL_TIMEOUT_S}s")
        data = await check_status(runpod_job_id)
        status = data.get("status", "")
        if status == "COMPLETED":
            return {"status": "COMPLETED", "output": data.get("output", {})}
        if status in ("FAILED", "CANCELLED"):
            return {"status": status, "error": data.get("error", "RunPod job failed")}
        await asyncio.sleep(POLL_INTERVAL_S)
