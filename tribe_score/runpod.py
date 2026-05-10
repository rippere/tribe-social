"""RunPod pod lifecycle via GraphQL API."""

import time
import requests
from dataclasses import dataclass

_GQL = "https://api.runpod.io/graphql"


@dataclass
class PodInfo:
    pod_id: str
    ssh_host: str
    ssh_port: int


def _gql(api_key: str, query: str, variables: dict | None = None) -> dict:
    resp = requests.post(
        _GQL,
        json={"query": query, "variables": variables or {}},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"RunPod API error: {data['errors']}")
    return data["data"]


def provision(api_key: str, gpu_type_id: str, image: str, disk_gb: int) -> str:
    mutation = """
    mutation Deploy($input: PodFindAndDeployOnDemandInput!) {
      podFindAndDeployOnDemand(input: $input) { id }
    }
    """
    data = _gql(api_key, mutation, {"input": {
        "cloudType":        "SECURE",
        "gpuCount":         1,
        "volumeInGb":       0,
        "containerDiskInGb": disk_gb,
        "minVcpuCount":     4,
        "minMemoryInGb":    15,
        "gpuTypeId":        gpu_type_id,
        "name":             "tribe-score",
        "imageName":        image,
        "ports":            "22/tcp",
        "supportPublicIp":  True,
        "startSsh":         True,
    }})
    return data["podFindAndDeployOnDemand"]["id"]


def get_ssh_info(api_key: str, pod_id: str) -> tuple[str, int] | None:
    """Returns (host, port) if SSH port is up, else None."""
    query = """
    query Pod($input: PodFilter!) {
      pod(input: $input) {
        desiredStatus
        runtime {
          ports { ip isIpPublic privatePort publicPort type }
        }
      }
    }
    """
    data = _gql(api_key, query, {"input": {"podId": pod_id}})
    pod = data.get("pod")
    if not pod or pod.get("desiredStatus") != "RUNNING":
        return None
    runtime = pod.get("runtime")
    if not runtime:
        return None
    for port in runtime.get("ports", []):
        if port.get("privatePort") == 22 and port.get("isIpPublic"):
            return port["ip"], port["publicPort"]
    return None


def wait_for_ssh(api_key: str, pod_id: str, timeout: int = 300) -> tuple[str, int]:
    """Poll until SSH port is reachable. Returns (host, port)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = get_ssh_info(api_key, pod_id)
        if result:
            return result
        time.sleep(10)
    raise TimeoutError(f"Pod {pod_id} did not expose SSH within {timeout}s")


def terminate(api_key: str, pod_id: str) -> None:
    mutation = """
    mutation Terminate($input: PodTerminateInput!) {
      podTerminate(input: $input)
    }
    """
    _gql(api_key, mutation, {"input": {"podId": pod_id}})
