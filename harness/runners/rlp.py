"""RLP sandbox worker backend (rlp-sdk Daytona-compatible client)."""

from __future__ import annotations

import json
import time
from typing import Any

from dotenv import load_dotenv
from rlp import Daytona

from harness.benchmarks import AGENT, BenchmarkSpec
from harness.common import apply_workload_payload
from harness.env_probe import (
    failed_env,
    host_env,
    merge_env,
    parse_probe_stdout,
    probe_shell_command,
)
from harness.paths import ROOT
from harness.rlp_config import resolve_rlp_client_config
from harness.rlp_create import build_rlp_resources, create_rlp_sandbox

# Native disk snaps typically bake the app under /home/daytona/app.
# The repo Dockerfile uses WORKDIR /app — registry boots must match.
SNAPSHOT_APP_DIR = "/home/daytona/app"
REGISTRY_APP_DIR = "/app"
DEFAULT_EXEC_TIMEOUT_S = 600


def _is_registry_image_ref(name_or_manifest: str) -> bool:
    """True for OCI/registry refs (not friendly native snapshot names)."""
    s = name_or_manifest.strip()
    if not s or s.startswith("snap-"):
        return False
    if s.startswith("sha256:"):
        return True
    return "/" in s or ":" in s


class RlpRunner:
    def __init__(
        self,
        *,
        spec: BenchmarkSpec = AGENT,
        snapshot: str | None = None,
        exec_timeout_s: int = DEFAULT_EXEC_TIMEOUT_S,
        target: str | None = None,
        toolbox_url: str | None = None,
        episodes_per_sandbox: int = 1,
        cpu: float = 1.0,
        cpu_max: float | None = None,
        memory: float | None = None,
        memory_max: float | None = None,
        disk: float | None = None,
    ) -> None:
        load_dotenv(ROOT / ".env")
        if episodes_per_sandbox < 1:
            raise ValueError("episodes_per_sandbox must be >= 1")
        if cpu <= 0:
            raise ValueError(f"cpu must be > 0, got {cpu}")
        if cpu_max is not None and cpu_max < cpu:
            raise ValueError(f"cpu_max ({cpu_max}) must be >= cpu ({cpu})")
        if memory_max is not None and memory is not None and memory_max < memory:
            raise ValueError(
                f"memory_max ({memory_max}) must be >= memory ({memory})"
            )
        self._spec = spec
        self._snapshot = snapshot or spec.boot_image_for_rlp(target)
        self._exec_timeout_s = exec_timeout_s
        self._target = target
        self._episodes_per_sandbox = episodes_per_sandbox
        mem = spec.memory_gib() if memory is None else memory
        disk_gib = max(2, mem) if disk is None else disk
        self._resources = build_rlp_resources(
            cpu=cpu,
            cpu_max=cpu_max,
            memory=mem,
            memory_max=memory_max,
            disk=disk_gib,
        )
        config = resolve_rlp_client_config(target, toolbox_url)
        self._client = Daytona(config)
        print(
            f"rlp client: target={getattr(config, 'target', None)!r} "
            f"api_url={getattr(config, 'api_url', None)!r} "
            f"toolbox_url={getattr(config, 'toolbox_url', None)!r} "
            f"benchmark={spec.id!r} episodes_per_sandbox={episodes_per_sandbox} "
            f"resources=cpu={cpu},cpu_max={cpu_max},memory={mem}GiB,"
            f"memory_max={memory_max},disk={disk_gib}GiB"
        )

        self._boot_image = self._snapshot.strip()
        self._registry_boot = _is_registry_image_ref(self._boot_image)
        self._create_timeout_s = 300 if self._registry_boot else 120
        self._app_dir = (
            REGISTRY_APP_DIR if self._registry_boot else SNAPSHOT_APP_DIR
        )
        self._run_env = spec.run_env(self._app_dir)
        self._agent_cmd = spec.agent_command()
        print(
            f"rlp boot image: {self._boot_image!r} "
            f"(registry={self._registry_boot}, app_dir={self._app_dir})"
        )

    def probe_env(self) -> dict[str, Any]:
        host = host_env()
        sandbox = None
        try:
            sandbox = self.create_sandbox()
            response = sandbox.process.exec(
                probe_shell_command(),
                timeout=60,
            )
            exit_code = int(response.exit_code or 0)
            stdout = (response.result or "").strip()
            if exit_code != 0:
                err = stdout or f"exit {exit_code}"
                print(f"warning: rlp env probe failed: {err[:200]}")
                return failed_env(host, probe="rlp", error=err[:500])
            remote = parse_probe_stdout(stdout)
            return merge_env(host, remote, probe="rlp")
        except Exception as exc:  # noqa: BLE001
            print(f"warning: rlp env probe failed: {exc}")
            return failed_env(host, probe="rlp", error=str(exc))
        finally:
            self.delete_sandbox(sandbox)

    def create_sandbox(self) -> Any:
        """Create one sandbox and wait until started. Does not exec or delete."""
        return create_rlp_sandbox(
            self._client,
            image=self._boot_image,
            resources=self._resources,
            timeout=self._create_timeout_s,
        )

    def delete_sandbox(self, sandbox: Any | None) -> None:
        if sandbox is None:
            return
        try:
            self._client.delete(sandbox)
        except Exception:  # noqa: BLE001, S110
            pass

    def exec_on_sandbox(
        self,
        sandbox: Any,
        n: int,
        seed: int,
        episodes: int,
        *,
        cold_first: bool,
        latency_origin: float | None = None,
    ) -> list[dict[str, Any]]:
        """Run ``episodes`` execs on an already-started sandbox.

        When ``cold_first`` is True (create-exec-delete workers), episode 0
        ``latency_ms`` includes create if ``latency_origin`` is the create
        start. Hold-then-exec passes ``cold_first=False`` so every episode is
        exec-only (``duration_ms`` is still the in-guest metric).
        """
        if episodes < 1:
            raise ValueError("episodes must be >= 1")
        sandbox_id = getattr(sandbox, "id", None)
        argv = " ".join(self._spec.agent_argv(n, seed))
        cmd = f"{self._agent_cmd} {argv}"
        records: list[dict[str, Any]] = []
        for episode_idx in range(episodes):
            cold = bool(cold_first and episode_idx == 0)
            if cold and latency_origin is not None:
                exec_start = latency_origin
            else:
                exec_start = time.monotonic()
            try:
                response = sandbox.process.exec(
                    cmd,
                    cwd=self._app_dir,
                    env=self._run_env,
                    timeout=self._exec_timeout_s,
                )
                exit_code = int(response.exit_code or 0)
                stdout = (response.result or "").strip()
                record: dict[str, Any] = {
                    "latency_ms": (time.monotonic() - exec_start) * 1000,
                    "exit_code": exit_code,
                    "sandbox_id": sandbox_id,
                    "target": self._target,
                    "benchmark": self._spec.id,
                    "episode_idx": episode_idx,
                    "cold": cold,
                    "fleet_hold": not cold_first,
                }
                if exit_code == 0:
                    try:
                        payload = json.loads(stdout)
                        apply_workload_payload(record, payload)
                    except json.JSONDecodeError:
                        record["error"] = "invalid_json_output"
                        record["stdout"] = stdout
                else:
                    record["stderr"] = stdout
                records.append(record)
            except Exception as exc:  # noqa: BLE001
                records.append(
                    {
                        "latency_ms": (time.monotonic() - exec_start) * 1000,
                        "exit_code": -1,
                        "error": f"{type(exc).__name__}: {exc}",
                        "target": self._target,
                        "benchmark": self._spec.id,
                        "sandbox_id": sandbox_id,
                        "episode_idx": episode_idx,
                        "cold": cold,
                        "fleet_hold": not cold_first,
                    }
                )
        return records

    def run_one(self, n: int, seed: int) -> dict[str, Any]:
        return self.run_episodes(n, seed, episodes=1)[0]

    def run_episodes(
        self, n: int, seed: int, episodes: int | None = None
    ) -> list[dict[str, Any]]:
        """Create once, exec ``episodes`` times, delete once.

        Episode 0 is cold (create + first exec). Later episodes are warm
        (exec-only ``latency_ms``). ``duration_ms`` remains the in-guest metric.
        """
        episodes = self._episodes_per_sandbox if episodes is None else episodes
        if episodes < 1:
            raise ValueError("episodes must be >= 1")

        records: list[dict[str, Any]] = []
        sandbox = None
        create_start = time.monotonic()
        try:
            sandbox = self.create_sandbox()
            return self.exec_on_sandbox(
                sandbox,
                n,
                seed,
                episodes,
                cold_first=True,
                latency_origin=create_start,
            )
        except Exception as exc:  # noqa: BLE001
            if not records:
                return [
                    {
                        "latency_ms": (time.monotonic() - create_start) * 1000,
                        "exit_code": -1,
                        "error": f"{type(exc).__name__}: {exc}",
                        "target": self._target,
                        "benchmark": self._spec.id,
                        "episode_idx": 0,
                        "cold": True,
                        "fleet_hold": False,
                    }
                ]
            return records
        finally:
            self.delete_sandbox(sandbox)
