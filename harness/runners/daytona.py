"""Daytona sandbox worker backend (official daytona SDK).

Supports container sandboxes (default) and Linux VM sandboxes
(``--runner daytona-vm`` / ``daytona-vm-hot``).

VM region default is ``us-west-3`` (eng: stock VM snaps are not in ``us``).
Cold VM snaps boot from disk; hot (memory) snaps are RLP-ish warm starts.
"""

from __future__ import annotations

import json
import time
from typing import Any, Literal

from daytona import CreateSandboxFromSnapshotParams, Daytona, DaytonaConfig
from dotenv import load_dotenv

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
from harness.runner_id import IFCONFIG_SHELL, parse_ifconfig_stdout, sdk_runner_id

APP_DIR = "/home/daytona/app"
DEFAULT_EXEC_TIMEOUT_S = 600
# Eng: VM seed snaps (daytona-vm-*) are available in us-west-3, not default us.
DEFAULT_VM_TARGET = "us-west-3"

SandboxKind = Literal["container", "vm"]
VmBoot = Literal["cold", "hot"]


def default_daytona_snapshot(
    spec: BenchmarkSpec,
    sandbox_kind: SandboxKind,
    *,
    vm_boot: VmBoot = "cold",
) -> str:
    if sandbox_kind == "vm":
        if vm_boot == "hot":
            return f"{spec.artifact_name}-vm-hot"
        return f"{spec.artifact_name}-vm"
    return spec.artifact_name


def resolve_daytona_target(
    sandbox_kind: SandboxKind,
    target: str | None,
) -> str | None:
    """VM runners default to us-west-3 when --target is omitted."""
    if target:
        return target
    if sandbox_kind == "vm":
        return DEFAULT_VM_TARGET
    return None


class DaytonaRunner:
    def __init__(
        self,
        *,
        spec: BenchmarkSpec = AGENT,
        snapshot: str | None = None,
        exec_timeout_s: int = DEFAULT_EXEC_TIMEOUT_S,
        target: str | None = None,
        episodes_per_sandbox: int = 1,
        sandbox_kind: SandboxKind = "container",
        vm_boot: VmBoot = "cold",
    ) -> None:
        load_dotenv(ROOT / ".env")
        if episodes_per_sandbox < 1:
            raise ValueError("episodes_per_sandbox must be >= 1")
        if sandbox_kind not in ("container", "vm"):
            raise ValueError(f"sandbox_kind must be 'container' or 'vm', got {sandbox_kind!r}")
        if vm_boot not in ("cold", "hot"):
            raise ValueError(f"vm_boot must be 'cold' or 'hot', got {vm_boot!r}")
        self._spec = spec
        self._sandbox_kind = sandbox_kind
        self._vm_boot = vm_boot
        if sandbox_kind == "vm":
            self._probe_label = "daytona-vm-hot" if vm_boot == "hot" else "daytona-vm"
        else:
            self._probe_label = "daytona"
        self._snapshot = snapshot or default_daytona_snapshot(
            spec, sandbox_kind, vm_boot=vm_boot
        )
        self._exec_timeout_s = exec_timeout_s
        self._target = resolve_daytona_target(sandbox_kind, target)
        self._episodes_per_sandbox = episodes_per_sandbox
        self._run_env = spec.run_env(APP_DIR)
        self._agent_cmd = spec.agent_command()
        config = DaytonaConfig(connection_pool_maxsize=None)
        if self._target:
            config = DaytonaConfig(connection_pool_maxsize=None, target=self._target)
        self._client = Daytona(config)
        print(
            f"{self._probe_label} client: target={self._target!r} "
            f"snapshot={self._snapshot!r} benchmark={spec.id!r} "
            f"sandbox_kind={sandbox_kind!r} vm_boot={vm_boot!r} "
            f"episodes_per_sandbox={episodes_per_sandbox}"
        )

    def _create_sandbox(self, *, timeout: int = 120):
        return self._client.create(
            CreateSandboxFromSnapshotParams(
                snapshot=self._snapshot,
                ephemeral=True,
                language="python",
            ),
            timeout=timeout,
        )

    def _resolve_runner_id(self, sandbox) -> tuple[str | None, str | None]:
        """SDK runner_id first; VM sandboxes fall back to curl ifconfig.net."""
        rid = sdk_runner_id(sandbox)
        if rid:
            return rid, "sdk"
        if self._sandbox_kind != "vm":
            return None, None
        try:
            response = sandbox.process.exec(IFCONFIG_SHELL, timeout=15)
            exit_code = int(response.exit_code or 0)
            stdout = (response.result or "").strip()
            if exit_code != 0:
                print(
                    f"warning: {self._probe_label} ifconfig runner probe "
                    f"failed: {(stdout or f'exit {exit_code}')[:200]}"
                )
                return None, None
            ip = parse_ifconfig_stdout(stdout)
            if not ip:
                print(
                    f"warning: {self._probe_label} ifconfig runner probe "
                    f"unparseable: {stdout[:200]}"
                )
                return None, None
            return ip, "ifconfig"
        except Exception as exc:  # noqa: BLE001
            print(f"warning: {self._probe_label} ifconfig runner probe failed: {exc}")
            return None, None

    def probe_env(self) -> dict[str, Any]:
        host = host_env()
        sandbox = None
        try:
            sandbox = self._create_sandbox(timeout=120)
            response = sandbox.process.exec(
                probe_shell_command(),
                timeout=60,
            )
            exit_code = int(response.exit_code or 0)
            stdout = (response.result or "").strip()
            if exit_code != 0:
                err = stdout or f"exit {exit_code}"
                print(f"warning: {self._probe_label} env probe failed: {err[:200]}")
                return failed_env(host, probe=self._probe_label, error=err[:500])
            remote = parse_probe_stdout(stdout)
            return merge_env(host, remote, probe=self._probe_label)
        except Exception as exc:  # noqa: BLE001
            print(f"warning: {self._probe_label} env probe failed: {exc}")
            return failed_env(host, probe=self._probe_label, error=str(exc))
        finally:
            if sandbox is not None:
                try:
                    self._client.delete(sandbox)
                except Exception:  # noqa: BLE001, S110
                    pass

    def run_one(self, n: int, seed: int) -> dict[str, Any]:
        return self.run_episodes(n, seed, episodes=1)[0]

    def run_episodes(
        self, n: int, seed: int, episodes: int | None = None
    ) -> list[dict[str, Any]]:
        """Create once, exec ``episodes`` times, delete once.

        Episode 0 is cold (create + first exec in ``latency_ms``). Later episodes
        are warm (exec-only ``latency_ms``). ``duration_ms`` is always in-sandbox.
        """
        episodes = self._episodes_per_sandbox if episodes is None else episodes
        if episodes < 1:
            raise ValueError("episodes must be >= 1")

        records: list[dict[str, Any]] = []
        sandbox = None
        create_start = time.monotonic()
        try:
            sandbox = self._create_sandbox(timeout=120)
            sandbox_id = sandbox.id
            runner_id, runner_id_source = sdk_runner_id(sandbox), "sdk"
            if not runner_id:
                runner_id_source = None
            argv = " ".join(self._spec.agent_argv(n, seed))
            cmd = f"{self._agent_cmd} {argv}"

            for episode_idx in range(episodes):
                cold = episode_idx == 0
                exec_start = time.monotonic() if not cold else create_start
                try:
                    response = sandbox.process.exec(
                        cmd,
                        cwd=APP_DIR,
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
                        "sandbox_kind": self._sandbox_kind,
                        "vm_boot": self._vm_boot if self._sandbox_kind == "vm" else None,
                        "episode_idx": episode_idx,
                        "cold": cold,
                    }
                    if runner_id:
                        record["runner_id"] = runner_id
                        record["runner_id_source"] = runner_id_source
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
                    fail_record: dict[str, Any] = {
                        "latency_ms": (time.monotonic() - exec_start) * 1000,
                        "exit_code": -1,
                        "error": f"{type(exc).__name__}: {exc}",
                        "target": self._target,
                        "benchmark": self._spec.id,
                        "sandbox_kind": self._sandbox_kind,
                        "vm_boot": self._vm_boot if self._sandbox_kind == "vm" else None,
                        "sandbox_id": sandbox_id,
                        "episode_idx": episode_idx,
                        "cold": cold,
                    }
                    if runner_id:
                        fail_record["runner_id"] = runner_id
                        fail_record["runner_id_source"] = runner_id_source
                    records.append(fail_record)
            if not runner_id:
                runner_id, runner_id_source = self._resolve_runner_id(sandbox)
            if runner_id:
                for rec in records:
                    rec.setdefault("runner_id", runner_id)
                    rec.setdefault("runner_id_source", runner_id_source)
            return records
        except Exception as exc:  # noqa: BLE001
            if not records:
                return [
                    {
                        "latency_ms": (time.monotonic() - create_start) * 1000,
                        "exit_code": -1,
                        "error": f"{type(exc).__name__}: {exc}",
                        "target": self._target,
                        "benchmark": self._spec.id,
                        "sandbox_kind": self._sandbox_kind,
                        "vm_boot": self._vm_boot if self._sandbox_kind == "vm" else None,
                        "episode_idx": 0,
                        "cold": True,
                    }
                ]
            return records
        finally:
            if sandbox is not None:
                try:
                    self._client.delete(sandbox)
                except Exception:  # noqa: BLE001, S110
                    pass
