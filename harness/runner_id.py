"""Identify the physical Daytona runner a sandbox landed on.

Prefer the SDK ``sandbox.runner_id`` field. If it is missing (common on some
VM create responses), fall back to the sandbox's public egress IP via
``curl ifconfig.net`` (Python urllib if curl is absent).
"""

from __future__ import annotations

import ipaddress
import re
from typing import Any, Literal

RunnerIdSource = Literal["sdk", "ifconfig"]

# Eng fallback: public egress IP as a runner fingerprint.
IFCONFIG_SHELL = (
    "curl -fsS --max-time 5 ifconfig.net "
    "|| python -c "
    "\"import urllib.request; "
    "print(urllib.request.urlopen('http://ifconfig.net', timeout=5)"
    ".read().decode().strip())\""
)


def sdk_runner_id(sandbox: Any) -> str | None:
    """Return Daytona ``runner_id`` if the SDK object exposes a non-empty value."""
    rid = getattr(sandbox, "runner_id", None)
    if rid is None:
        dto = getattr(sandbox, "_sandbox", None) or getattr(sandbox, "instance", None)
        rid = getattr(dto, "runner_id", None) if dto is not None else None
    if rid is None:
        return None
    text = str(rid).strip()
    return text or None


def parse_ifconfig_stdout(stdout: str) -> str | None:
    """Extract a single IPv4/IPv6 address from ifconfig.net-style stdout."""
    text = (stdout or "").strip()
    if not text:
        return None
    line = text.splitlines()[-1].strip()
    line = re.sub(r"\s+", "", line)
    try:
        return str(ipaddress.ip_address(line))
    except ValueError:
        return None


def distinct_runner_ids(records: list[dict[str, Any]]) -> list[str]:
    """Stable unique runner_id values (skip missing)."""
    seen: set[str] = set()
    ordered: list[str] = []
    for record in records:
        rid = record.get("runner_id")
        if not rid:
            continue
        key = str(rid)
        if key not in seen:
            seen.add(key)
            ordered.append(key)
    return ordered
