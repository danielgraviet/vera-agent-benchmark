"""RLP sandbox create via SDK ``CreateSandboxFromImageParams``.

Sends ``cpu_arch`` / ``cpu_type`` / ``mode`` from the target profile so ARM64
and Vera cells get the right placement (see ``harness.regions``).
"""

from __future__ import annotations

import inspect
from typing import Any

from rlp import CreateSandboxFromImageParams, Daytona, Resources
from rlp.sandbox import Sandbox

from harness.regions import (
    require_sdk_field,
    resolve_rlp_cpu_arch,
    resolve_rlp_cpu_type,
    resolve_rlp_mode,
)

# Eng API maps cpu_max → vcpus_max; some SDK checkouts use one name or the other.
_CPU_MAX_ALIASES = ("cpu_max", "vcpus_max", "max_cpu")
_MEM_MAX_ALIASES = ("memory_max", "mem_max", "max_memory")


def _resources_param_names() -> set[str]:
    names: set[str] = set()
    names.update(getattr(Resources, "__dataclass_fields__", {}) or {})
    model_fields = getattr(Resources, "model_fields", None)
    if isinstance(model_fields, dict):
        names.update(model_fields)
    try:
        for name, param in inspect.signature(Resources).parameters.items():
            if name == "self":
                continue
            if param.kind is inspect.Parameter.VAR_KEYWORD:
                names.add("**")
            else:
                names.add(name)
    except (TypeError, ValueError):
        pass
    return names


def _pick_alias(wanted: tuple[str, ...], available: set[str]) -> str | None:
    for name in wanted:
        if name in available:
            return name
    return None


def build_rlp_resources(
    *,
    cpu: float,
    memory: int | float,
    disk: int | float,
    cpu_max: float | None = None,
    memory_max: int | float | None = None,
) -> Resources:
    """Build ``Resources``, mapping burst caps onto whatever names this SDK has."""
    available = _resources_param_names()
    kwargs: dict[str, Any] = {"cpu": cpu, "memory": memory, "disk": disk}
    extra: list[tuple[tuple[str, ...], float | int | None]] = [
        (_CPU_MAX_ALIASES, cpu_max),
        (_MEM_MAX_ALIASES, memory_max),
    ]
    allow_extra = "**" in available
    for aliases, value in extra:
        if value is None:
            continue
        name = _pick_alias(aliases, available)
        if name is None and allow_extra:
            name = aliases[0]
        if name is None:
            have = ", ".join(sorted(n for n in available if n != "**")) or "(none)"
            print(
                f"rlp resources: SDK has no {aliases[0]} (tried {', '.join(aliases)}; "
                f"fields={have}). Sending guarantee only; burst cap is the cell "
                f"RLP_BURST_MAX_* default, not this flag.",
                flush=True,
            )
            continue
        kwargs[name] = value
    if allow_extra:
        return Resources(**kwargs)
    return Resources(**{k: v for k, v in kwargs.items() if k in available})


def create_rlp_sandbox(
    client: Daytona,
    *,
    image: str,
    timeout: int = 60,
    resources: Resources | None = None,
    cpu_arch: str | None = None,
    cpu_type: str | None = None,
    mode: str | None = None,
    name: str | None = None,
    target: str | None = None,
    omit_mode: bool = False,
) -> Sandbox:
    """Create a sandbox and wait until started.

    Defaults from ``target`` when omitted:
    - ``arm64-test-1`` / ``vera`` → ``cpu_arch=arm64``
    - ``vera`` → ``cpu_type=vera``, ``mode=dedicated`` (skipped when
      ``omit_mode`` — burstable creates must not reserve a full vCPU)
    """
    if cpu_arch is None:
        cpu_arch = resolve_rlp_cpu_arch(target)
    if cpu_type is None:
        cpu_type = resolve_rlp_cpu_type(target)
    if omit_mode:
        mode = None
    elif mode is None:
        mode = resolve_rlp_mode(target)

    if cpu_arch is not None:
        require_sdk_field(
            CreateSandboxFromImageParams,
            "cpu_arch",
            purpose=f"cpu_arch={cpu_arch!r}",
        )
    if cpu_type is not None:
        require_sdk_field(
            CreateSandboxFromImageParams,
            "cpu_type",
            purpose=f"cpu_type={cpu_type!r}",
        )

    params = _create_params(
        image=image,
        name=name,
        resources=resources,
        cpu_arch=cpu_arch,
        cpu_type=cpu_type,
        mode=mode,
    )
    region = getattr(client, "_target", None)
    def _first(*names: str) -> Any:
        for name in names:
            if hasattr(resources, name):
                return getattr(resources, name)
        return None

    print(
        f"rlp create: region={region!r} cpu_arch={cpu_arch!r} "
        f"cpu_type={cpu_type!r} mode={mode!r} image={image!r} "
        f"cpu={getattr(resources, 'cpu', None)!r} "
        f"cpu_max={_first(*_CPU_MAX_ALIASES)!r} "
        f"memory={getattr(resources, 'memory', None)!r} "
        f"memory_max={_first(*_MEM_MAX_ALIASES)!r} "
        f"disk={getattr(resources, 'disk', None)!r}",
        flush=True,
    )
    sandbox = client.create(params, timeout=timeout)
    print(
        f"rlp create started: id={getattr(sandbox, 'id', None)!r}",
        flush=True,
    )
    return sandbox


def _create_params(**kwargs: Any) -> CreateSandboxFromImageParams:
    """Pass only kwargs the installed SDK dataclass accepts (skip None)."""
    fields = CreateSandboxFromImageParams.__dataclass_fields__
    return CreateSandboxFromImageParams(
        **{k: v for k, v in kwargs.items() if k in fields and v is not None}
    )
