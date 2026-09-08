"""Host + in-sandbox hardware probe for JSONL meta.env labeling."""

from __future__ import annotations

import base64
import json
import platform
import subprocess
from typing import Any

# Inline script run inside docker/sandbox images (stdlib only).
PROBE_PY = r"""
import json, os, platform
from pathlib import Path

def parse_cpuinfo(text: str) -> str:
    model = hardware = cpu_part = ""
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "model name" and not model:
            model = val
        elif key == "hardware" and not hardware:
            hardware = val
        elif key == "cpu part" and not cpu_part:
            cpu_part = val
    return model or hardware or cpu_part or ""

cpu_model = ""
cpuinfo = Path("/proc/cpuinfo")
if cpuinfo.is_file():
    try:
        cpu_model = parse_cpuinfo(cpuinfo.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        cpu_model = ""
if not cpu_model:
    cpu_model = (platform.processor() or "").strip() or "unknown"

print(json.dumps({
    "arch": platform.machine(),
    "cpu_model": cpu_model,
    "cpu_count": os.cpu_count(),
    "platform": platform.platform(),
}, separators=(",", ":")))
""".strip()


def probe_shell_command(python: str = "python") -> str:
    """Shell-safe one-liner that runs PROBE_PY (avoids quoting multiline -c)."""
    b64 = base64.b64encode(PROBE_PY.encode("utf-8")).decode("ascii")
    return (
        f"{python} -c "
        f'"import base64; exec(base64.b64decode({b64!r}).decode())"'
    )


def parse_cpuinfo(text: str) -> str:
    """Extract a stable CPU label from /proc/cpuinfo text."""
    model = hardware = cpu_part = ""
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "model name" and not model:
            model = val
        elif key == "hardware" and not hardware:
            hardware = val
        elif key == "cpu part" and not cpu_part:
            cpu_part = val
    return model or hardware or cpu_part or "unknown"


def host_env() -> dict[str, Any]:
    """Harness-process view (useful for Docker-on-Mac Apple chip labels)."""
    host_cpu: str | None = None
    if platform.system() == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            if result.returncode == 0:
                brand = (result.stdout or "").strip()
                host_cpu = brand or None
        except (OSError, subprocess.TimeoutExpired):
            host_cpu = None
    return {
        "host_arch": platform.machine(),
        "host_cpu": host_cpu,
    }


def merge_env(
    host: dict[str, Any],
    remote: dict[str, Any] | None,
    *,
    probe: str,
    probe_error: str | None = None,
) -> dict[str, Any]:
    """Stable meta.env shape; remote fields optional on failure / skip."""
    env: dict[str, Any] = {
        "arch": None,
        "cpu_model": None,
        "cpu_count": None,
        "platform": None,
        "host_arch": host.get("host_arch"),
        "host_cpu": host.get("host_cpu"),
        "probe": probe,
    }
    if remote:
        for key in ("arch", "cpu_model", "cpu_count", "platform"):
            if key in remote and remote[key] is not None:
                env[key] = remote[key]
    if probe_error:
        env["cpu_model"] = env["cpu_model"] or "probe_failed"
        env["probe_error"] = probe_error
    return env


def parse_probe_stdout(stdout: str) -> dict[str, Any]:
    """Parse one JSON object from probe script stdout."""
    text = (stdout or "").strip()
    if not text:
        raise ValueError("empty probe stdout")
    line = text.splitlines()[-1]
    data = json.loads(line)
    if not isinstance(data, dict):
        raise ValueError(f"probe stdout is not an object: {data!r}")
    return data


def failed_env(host: dict[str, Any], *, probe: str, error: str) -> dict[str, Any]:
    return merge_env(host, None, probe=probe, probe_error=error)


def skipped_env(host: dict[str, Any]) -> dict[str, Any]:
    return merge_env(host, None, probe="skipped")
