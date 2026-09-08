"""Helpers to create Daytona sandbox snapshots (cold disk vs hot memory)."""

from __future__ import annotations

from daytona._utils.timeout import http_timeout
from daytona.common.sandbox import SandboxState
from daytona_api_client.models.create_sandbox_snapshot import CreateSandboxSnapshot


def create_named_snapshot(
    sandbox,
    name: str,
    *,
    include_memory: bool = False,
    timeout: float = 600,
) -> None:
    """Create a named snapshot from ``sandbox``.

    Cold (``include_memory=False``): VM must be STOPPED — filesystem only.
    Hot (``include_memory=True``): VM must be STARTED — filesystem + memory
    (RLP-ish warm boot). SDK ``create_snapshot`` does not expose includeMemory
    yet, so we call the API client directly.
    """
    response = sandbox._sandbox_api.create_sandbox_snapshot(
        sandbox.id,
        CreateSandboxSnapshot(name=name, include_memory=include_memory),
        _request_timeout=http_timeout(timeout),
    )
    # Mirror Sandbox.create_snapshot post-processing / wait.
    process = getattr(sandbox, "_Sandbox__process_sandbox_dto", None)
    if callable(process):
        process(response)
    else:
        sandbox.refresh_data()

    error_states = [SandboxState.ERROR, SandboxState.BUILD_FAILED]
    exclude = {SandboxState.SNAPSHOTTING} | set(error_states)
    target_states = [s for s in SandboxState if s not in exclude]
    sandbox._wait_for_state(target_states, error_states)
