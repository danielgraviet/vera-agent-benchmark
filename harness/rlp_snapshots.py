"""RLP native disk-snapshot helpers.

RLP has two different "snapshot" concepts:

1. Daytona-dialect image aliases — ``/daytona/snapshots`` (OCI/NFS manifests
   referenced by friendly name).
2. Native VM disk snapshots — ``/snapshots`` (created via
   ``sandbox.create_snapshot``). These are what the RLP web UI shows.

Native snapshots are addressed on create by ``manifest_name``
(e.g. ``snap-<uuid>``), NOT the friendly ``name``. Passing the friendly name
as ``image`` yields: manifest \"…\" not found on NFS.
"""

from __future__ import annotations

import time
from typing import Any

from rlp import Daytona
from rlp.errors import DaytonaError


def list_native_snapshots(client: Daytona) -> list[dict[str, Any]]:
    data = client._api.get("/snapshots").json()
    return list(data.get("snapshots") or [])


def get_native_snapshot(client: Daytona, name: str) -> dict[str, Any] | None:
    matches = [s for s in list_native_snapshots(client) if s.get("name") == name]
    if not matches:
        return None
    # Prefer a ready snapshot if several share the name.
    ready = [s for s in matches if s.get("status") == "ready"]
    return (ready or matches)[0]


def is_registry_image_ref(name_or_manifest: str) -> bool:
    """True for Docker Hub / GHCR / digest refs (not native snap names)."""
    s = name_or_manifest.strip()
    if not s:
        return False
    if s.startswith("snap-"):
        return False
    if s.startswith("sha256:"):
        return True
    # user/repo, registry.example/…, docker.io/…
    return "/" in s


def resolve_boot_image(client: Daytona, name_or_manifest: str) -> str:
    """Map a friendly snapshot name to the NFS ``manifest_name`` used by POST /vms.

    Registry refs (e.g. ``dtgraviet/vera-agent-benchmark-rl:latest``) pass
    through unchanged so RLP can pull OCI images without a native snapshot.
    """
    if name_or_manifest.startswith("snap-") or is_registry_image_ref(name_or_manifest):
        return name_or_manifest

    snap = get_native_snapshot(client, name_or_manifest)
    if snap is None:
        raise DaytonaError(
            f"Native RLP snapshot {name_or_manifest!r} not found on /snapshots. "
            "Build it with: uv run scripts/build_rlp_snapshot.py "
            "(or pass a registry image as --snapshot, e.g. user/image:tag)"
        )
    if snap.get("status") != "ready":
        raise DaytonaError(
            f"Native RLP snapshot {name_or_manifest!r} is not ready "
            f"(status={snap.get('status')!r}, error={snap.get('error')!r})"
        )
    manifest = snap.get("manifest_name")
    if not manifest:
        raise DaytonaError(
            f"Native RLP snapshot {name_or_manifest!r} has no manifest_name: {snap}"
        )
    return str(manifest)


def delete_native_snapshot_if_exists(client: Daytona, name: str) -> None:
    for snap in list_native_snapshots(client):
        if snap.get("name") != name:
            continue
        snap_id = snap.get("id")
        if not snap_id:
            continue
        print(
            f"Deleting existing native snapshot {name!r} "
            f"(id={snap_id}, status={snap.get('status')}) …"
        )
        try:
            client._api.delete(f"/snapshots/{snap_id}")
        except DaytonaError as exc:
            print(f"Warning: failed to delete snapshot {snap_id}: {exc}")


def wait_for_native_snapshot(
    client: Daytona,
    name: str,
    *,
    snapshot_id: str | None = None,
    timeout_s: int = 600,
) -> dict[str, Any]:
    """Poll native ``/snapshots`` until the named (or id) snapshot is ready."""
    terminal_bad = {"error", "failed"}
    start = time.time()
    last = None
    while True:
        snaps = list_native_snapshots(client)
        if snapshot_id:
            match = next((s for s in snaps if s.get("id") == snapshot_id), None)
        else:
            match = next((s for s in snaps if s.get("name") == name), None)

        status = (match or {}).get("status")
        if status != last:
            print(f"native snapshot {name!r} status={status}")
            last = status

        if match and status == "ready":
            return match
        if match and status in terminal_bad:
            raise RuntimeError(
                f"Native snapshot {name!r} failed: status={status} "
                f"error={match.get('error')}"
            )
        if time.time() - start > timeout_s:
            raise TimeoutError(
                f"Timed out waiting for native snapshot {name!r} "
                f"(last status={status!r})"
            )
        time.sleep(2)
