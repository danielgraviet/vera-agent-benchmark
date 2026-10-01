"""Host + in-sandbox hardware probe for JSONL ``meta.env`` labeling."""

from __future__ import annotations

import base64
import json
import platform
import subprocess
from typing import Any

# Stdlib-only script executed inside the sandbox (base64-wrapped for quoting).
_PROBE_PY = """
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
    """Return a shell one-liner that runs the in-sandbox probe script."""
    b64 = base64.b64encode(_PROBE_PY.encode("utf-8")).decode("ascii")
    return (
        f"{python} -c "
        f'"import base64; exec(base64.b64decode({b64!r}).decode())"'
    )


def host_env() -> dict[str, Any]:
    """Harness-host labels (e.g. Apple Silicon brand via sysctl on Darwin)."""
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
    """Build the stable ``meta.env`` object (remote fields optional)."""
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
            if remote.get(key) is not None:
                env[key] = remote[key]
    if probe_error:
        env["cpu_model"] = env["cpu_model"] or "probe_failed"
        env["probe_error"] = probe_error
    return env


def parse_probe_stdout(stdout: str) -> dict[str, Any]:
    """Parse the probe script's JSON object from sandbox stdout."""
    text = (stdout or "").strip()
    if not text:
        raise ValueError("empty probe stdout")
    data = json.loads(text.splitlines()[-1])
    if not isinstance(data, dict):
        raise ValueError(f"probe stdout is not an object: {data!r}")  # noqa: TRY004
    return data


def failed_env(host: dict[str, Any], *, probe: str, error: str) -> dict[str, Any]:
    return merge_env(host, None, probe=probe, probe_error=error)


def skipped_env(host: dict[str, Any]) -> dict[str, Any]:
    return merge_env(host, None, probe="skipped")
