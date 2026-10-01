"""RLP client config helpers.

``--target`` and ``--toolbox-url`` are optional passthroughs to
``DaytonaConfig``. Credentials and the default API URL come from the SDK
environment (for example ``RLP_API_KEY`` / ``RLP_API_URL``).
"""

from __future__ import annotations

from typing import Any

from rlp import DaytonaConfig


def resolve_rlp_client_config(
    target: str | None = None,
    toolbox_url: str | None = None,
) -> DaytonaConfig:
    """Build an RLP ``DaytonaConfig`` from optional CLI overrides."""
    return _daytona_config(target=target, toolbox_url=toolbox_url)


def _daytona_config(**kwargs: Any) -> DaytonaConfig:
    """Build ``DaytonaConfig``, dropping unknown or ``None`` kwargs."""
    fields = getattr(DaytonaConfig, "__dataclass_fields__", {})
    return DaytonaConfig(
        **{k: v for k, v in kwargs.items() if k in fields and v is not None}
    )
