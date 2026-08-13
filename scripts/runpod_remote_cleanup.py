from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


PREFIX_PATTERN = re.compile(r"^automatic-video-ai-[a-f0-9]{12}$")


class CleanupError(RuntimeError):
    pass


class RunPodCleanupClient:
    def __init__(self, api_key: str, base_url: str = "https://api.runpod.io") -> None:
        if not api_key:
            raise CleanupError("RUNPOD_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers=self.headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[-1000:]
            if exc.code == 404 and method == "DELETE":
                return {}
            raise CleanupError(f"RunPod HTTP {exc.code} for {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise CleanupError(f"RunPod network error for {path}: {exc}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CleanupError(f"RunPod returned invalid JSON for {path}") from exc

    def _graphql(self, query: str) -> dict[str, Any]:
        payload = self._request("POST", "/graphql", {"query": query})
        errors = payload.get("errors", []) if isinstance(payload, dict) else []
        if errors:
            detail = json.dumps(errors, ensure_ascii=False)
            if "not found" in detail.lower() or "does not exist" in detail.lower():
                return {"absent": True}
            raise CleanupError(f"RunPod GraphQL error: {detail[-1500:]}")
        return payload.get("data", {}) if isinstance(payload, dict) else {}

    def _list_rest(self, path: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            query: dict[str, Any] = {"limit": 100}
            if cursor:
                query["cursor"] = cursor
            payload = self._request("GET", f"{path}?{urllib.parse.urlencode(query)}")
            page = payload if isinstance(payload, list) else payload.get("items", [])
            items.extend(item for item in page if isinstance(item, dict))
            if not isinstance(payload, dict):
                return items
            pagination = payload.get("pagination", {})
            cursor = pagination.get("nextCursor") or payload.get("nextCursor")
            if not cursor:
                return items

    def matching_inventory(self, prefix: str) -> dict[str, list[dict[str, Any]]]:
        data = self._graphql("query { myself { endpoints { id name } } }")
        endpoints = ((data.get("myself") or {}).get("endpoints") or []) if isinstance(data, dict) else []
        resources = {
            "endpoint": [item for item in endpoints if isinstance(item, dict)],
            "pod": self._list_rest("/v2/pods"),
            "network_volume": self._list_rest("/v2/network-volumes"),
        }
        return {
            kind: [item for item in values if str(item.get("name") or "").startswith(prefix)]
            for kind, values in resources.items()
        }

    def delete_endpoint(self, endpoint_id: str) -> None:
        escaped = endpoint_id.replace('"', '\\"')
        updated = self._graphql(
            "mutation { saveEndpoint(input: { "
            f'id: "{escaped}", workersMin: 0, workersMax: 0'
            " }) { id } }"
        )
        if not updated.get("absent"):
            self._graphql(f'mutation {{ deleteEndpoint(id: "{escaped}") }}')

    def delete_rest(self, path: str, resource_id: str) -> None:
        self._request("DELETE", f"{path}/{urllib.parse.quote(resource_id, safe='')}")


def cleanup_until_absent(
    client: RunPodCleanupClient,
    prefix: str,
    *,
    attempts: int = 120,
    retry_seconds: float = 15.0,
) -> dict[str, int]:
    if not PREFIX_PATTERN.fullmatch(prefix):
        raise CleanupError("resource prefix does not match the exact automatic-video-ai lease format")
    last_error = ""
    for attempt in range(attempts):
        try:
            inventory = client.matching_inventory(prefix)
            for item in inventory["endpoint"]:
                client.delete_endpoint(str(item["id"]))
            for item in inventory["pod"]:
                client.delete_rest("/v2/pods", str(item["id"]))
            for item in inventory["network_volume"]:
                client.delete_rest("/v2/network-volumes", str(item["id"]))
            remaining = client.matching_inventory(prefix)
            counts = {kind: len(items) for kind, items in remaining.items()}
            if not any(counts.values()):
                return counts
            last_error = f"matching resources remain: {json.dumps(counts, sort_keys=True)}"
        except Exception as exc:
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(retry_seconds)
    raise CleanupError(f"remote cleanup did not converge: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete only RunPod resources matching one exact lease prefix")
    parser.add_argument("--prefix", required=True)
    parser.add_argument("--delay-minutes", type=int, required=True)
    parser.add_argument("--attempts", type=int, default=120)
    parser.add_argument("--retry-seconds", type=float, default=15.0)
    args = parser.parse_args()
    if not PREFIX_PATTERN.fullmatch(args.prefix):
        raise CleanupError("invalid resource prefix")
    if args.delay_minutes < 1 or args.delay_minutes > 240:
        raise CleanupError("delay-minutes must be between 1 and 240")
    time.sleep(args.delay_minutes * 60)
    client = RunPodCleanupClient(os.environ.get("RUNPOD_API_KEY", ""))
    counts = cleanup_until_absent(
        client,
        args.prefix,
        attempts=args.attempts,
        retry_seconds=args.retry_seconds,
    )
    print(json.dumps({"prefix": args.prefix, "remaining": counts}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
