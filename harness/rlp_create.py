"""RLP sandbox create helpers."""

from __future__ import annotations

from typing import Any

from rlp import CreateSandboxFromImageParams, Daytona, Resources
from rlp.sandbox import Sandbox


def _accepted_fields(cls: type) -> set[str]:
    names = set(getattr(cls, "__dataclass_fields__", {}) or {})
    model_fields = getattr(cls, "model_fields", None)
    if isinstance(model_fields, dict):
        names.update(model_fields)
    return names


def _filter_kwargs(cls: type, kwargs: dict[str, Any]) -> dict[str, Any]:
    fields = _accepted_fields(cls)
    return {k: v for k, v in kwargs.items() if k in fields and v is not None}


def build_rlp_resources(
    *,
    cpu: float,
    memory: float,
    disk: float,
    cpu_max: float | None = None,
    memory_max: float | None = None,
) -> Resources:
    """Build ``Resources`` for sandbox create (drops unknown SDK fields)."""
    return Resources(
        **_filter_kwargs(
            Resources,
            {
                "cpu": cpu,
                "memory": memory,
                "disk": disk,
                "cpu_max": cpu_max,
                "memory_max": memory_max,
            },
        )
    )


def create_rlp_sandbox(
    client: Daytona,
    *,
    image: str,
    timeout: int = 60,
    resources: Resources | None = None,
    name: str | None = None,
) -> Sandbox:
    """Create a sandbox from ``image`` and wait until started."""
    params = CreateSandboxFromImageParams(
        **_filter_kwargs(
            CreateSandboxFromImageParams,
            {"image": image, "name": name, "resources": resources},
        )
    )
    print(
        f"rlp create: target={getattr(client, '_target', None)!r} "
        f"image={image!r} resources={resources!r}",
        flush=True,
    )
    sandbox = client.create(params, timeout=timeout)
    print(f"rlp create started: id={getattr(sandbox, 'id', None)!r}", flush=True)
    return sandbox
