"""Client-side throughput tuning for the RLP SDK (rlp-sdk / httpx).

Why this exists (measured on vera, 2026-08-21, 176 held sandboxes, ~1.1s
in-guest episodes; guest p50 identical in every configuration):

    client location        pool   exec tput   wall_p50 (guest ~1.15s)
    laptop via SSH tunnel   100      19.5/s   7.6s   <- ladder plateau
    laptop via SSH tunnel   600      30.6/s   6.6s   (tunnel TCP serializes)
    co-located (19ms RTT)   100      82.3/s   1.9s   (pool queueing only)
    co-located (19ms RTT)   600     128.9/s   1.2s   = guest + RTT, no throttle

Two SDK defaults cause the client-side plateau:

1. ``rlp.http.HttpClient`` builds ``httpx.Client`` with no ``limits`` ->
   httpx's default 100 max connections. Every harness worker shares one
   client, so at concurrency > ~100 exec dispatch queues client-side while
   the fleet idles. The plateau scales with (episode + RTT) x 100.

2. ``Sandbox.wait_until_started`` polls ``GET /vms/:id`` every 100ms per
   pending sandbox. A 352-wide create wave = ~3.5k req/s of polling sharing
   the same pool; raising the pool WITHOUT tempering the polls makes ladders
   WORSE (measured on phoenix: 24/s -> 9.8/s with pool=2000 and stock polls).

``apply()`` patches both, idempotently, tunable via env:

    RLP_HTTP_MAX_CONNECTIONS   pool size (default 512)
    RLP_WAIT_POLL_START_S      first wait_until_started poll interval (0.25)
    RLP_WAIT_POLL_FACTOR       backoff factor per poll (1.5)
    RLP_WAIT_POLL_MAX_S        poll interval ceiling (2.0)

The third contributor -- RTT -- cannot be patched: run the harness near the
cell for chip-grade numbers (rlp-control for vera, the phoenix cell API host
for us-phoenix-1). See RUNBOOK.md.
"""

from __future__ import annotations

import os
import time

import httpx
import rlp.http as rlp_http
import rlp.sandbox as rlp_sandbox
from rlp.errors import DaytonaError, DaytonaTimeoutError, DaytonaValidationError


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def apply() -> None:
    """Patch the installed SDK in-process. Safe to call more than once."""
    if getattr(apply, "_done", False):
        return
    apply._done = True  # type: ignore[attr-defined]

    max_conn = int(_env_f("RLP_HTTP_MAX_CONNECTIONS", 512))

    # -- 1. connection pool ---------------------------------------------------
    # Rebuild the inner httpx.Client with explicit limits, mirroring the SDK's
    # own construction (rlp/http.py): same base_url, headers, and timeout.
    orig_init = rlp_http.HttpClient.__init__

    def pooled_init(self, base_url, api_key, source="rlp-sdk-python"):  # type: ignore[no-untyped-def]
        orig_init(self, base_url, api_key, source)
        old = self._client
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers=dict(old.headers),
            timeout=httpx.Timeout(30.0, read=None),
            limits=httpx.Limits(
                max_connections=max_conn, max_keepalive_connections=max_conn
            ),
        )
        old.close()

    rlp_http.HttpClient.__init__ = pooled_init

    # -- 2. wait_until_started poll cadence ------------------------------------
    # Same semantics as the SDK original (timeout handling, error states),
    # only the cadence differs: start at 0.25s (not 0.1s) and back off to a
    # 2s ceiling immediately (the SDK waits 5s before backing off, capped 1s).
    start_s = _env_f("RLP_WAIT_POLL_START_S", 0.25)
    factor = _env_f("RLP_WAIT_POLL_FACTOR", 1.5)
    max_s = _env_f("RLP_WAIT_POLL_MAX_S", 2.0)

    def tempered_wait(self, timeout: int = 60) -> None:  # type: ignore[no-untyped-def]
        if timeout < 0:
            raise DaytonaValidationError("Timeout must be a non-negative number")
        start = time.time()
        interval = start_s
        while self.state != "started":
            self.refresh_data()
            if self.state == "started":
                return
            if self.state == "error":
                raise DaytonaError(
                    f"Sandbox {self.id} failed to start "
                    f"(state={self.state}, reason={self.error_reason})"
                )
            if timeout != 0 and time.time() - start > timeout:
                raise DaytonaTimeoutError(
                    "Sandbox failed to become ready within the timeout period"
                )
            time.sleep(interval)
            interval = min(interval * factor, max_s)

    rlp_sandbox.Sandbox.wait_until_started = tempered_wait


def settings() -> dict[str, float | int]:
    """Env knobs currently in force (for JSONL meta; does not apply patches)."""
    return {
        "http_max_connections": int(_env_f("RLP_HTTP_MAX_CONNECTIONS", 512)),
        "wait_poll_start_s": _env_f("RLP_WAIT_POLL_START_S", 0.25),
        "wait_poll_factor": _env_f("RLP_WAIT_POLL_FACTOR", 1.5),
        "wait_poll_max_s": _env_f("RLP_WAIT_POLL_MAX_S", 2.0),
    }
