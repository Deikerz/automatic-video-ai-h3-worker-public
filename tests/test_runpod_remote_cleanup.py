import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "runpod_remote_cleanup.py"
SPEC = importlib.util.spec_from_file_location("runpod_remote_cleanup", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class FakeClient:
    def __init__(self):
        self.deleted = []
        self.inventories = [
            {
                "endpoint": [{"id": "endpoint-1", "name": "automatic-video-ai-abcdef123456-endpoint"}],
                "pod": [{"id": "pod-1", "name": "automatic-video-ai-abcdef123456-pod"}],
                "network_volume": [{"id": "volume-1", "name": "automatic-video-ai-abcdef123456-models"}],
            },
            {"endpoint": [], "pod": [], "network_volume": []},
        ]

    def matching_inventory(self, prefix):
        return self.inventories.pop(0)

    def delete_endpoint(self, resource_id):
        self.deleted.append(("endpoint", resource_id))

    def delete_rest(self, path, resource_id):
        self.deleted.append((path, resource_id))


def test_cleanup_is_scoped_to_exact_lease_prefix():
    client = FakeClient()

    result = MODULE.cleanup_until_absent(
        client,
        "automatic-video-ai-abcdef123456",
        attempts=1,
        retry_seconds=0,
    )

    assert result == {"endpoint": 0, "pod": 0, "network_volume": 0}
    assert client.deleted == [
        ("endpoint", "endpoint-1"),
        ("/v2/pods", "pod-1"),
        ("/v2/network-volumes", "volume-1"),
    ]


@pytest.mark.parametrize(
    "prefix",
    ["automatic-video-ai-", "automatic-video-ai-ABCDEF123456", "other-abcdef123456", ""],
)
def test_cleanup_rejects_broad_or_malformed_prefix(prefix):
    with pytest.raises(MODULE.CleanupError, match="exact"):
        MODULE.cleanup_until_absent(FakeClient(), prefix, attempts=1, retry_seconds=0)


def test_remote_cleanup_uses_rest_v2_for_endpoint_inventory_and_deletion():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '_list_rest("/v2/serverless")' in source
    assert '"PATCH",' in source
    assert '"workers": {"min": 0, "max": 0}' in source
    assert '"DELETE", f"/v2/serverless/{encoded}"' in source
