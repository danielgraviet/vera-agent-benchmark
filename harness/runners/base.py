"""Runner protocol: each backend exposes run_one(n, seed) -> result dict.

The suite types this as ``RunOne = Callable[[int, int], dict]`` for single-shot
backends. Daytona/RLP also expose ``run_episodes(n, seed, episodes)`` for
sandbox reuse (create once → exec E times → delete once).
"""

from __future__ import annotations

from typing import Any, Protocol


class Runner(Protocol):
    def run_one(self, n: int, seed: int) -> dict[str, Any]: ...
