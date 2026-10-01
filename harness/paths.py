"""Default JSONL output paths under data/<benchmark>/<series>/."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def rlp_cpu_series_suffix(cpu: float | None, cpu_max: float | None = None) -> str:
    """Return the suffix for fractional RLP series names."""
    parts: list[str] = []
    if cpu is not None and abs(float(cpu) - 1.0) >= 1e-9:
        text = f"{float(cpu):.6f}".rstrip("0").rstrip(".")
        parts.append("c" + text.replace(".", "p"))
    if cpu_max is not None:
        text = f"{float(cpu_max):.6f}".rstrip("0").rstrip(".")
        parts.append("max" + text.replace(".", "p"))
    if not parts:
        return ""
    return "-" + "-".join(parts)


def result_series_name(
    runner: str,
    target: str | None = None,
    *,
    rlp_cpu: float | None = None,
    rlp_cpu_max: float | None = None,
) -> str:
    """Map CLI runner + optional target to a results folder."""
    if runner == "rlp":
        base = "rlp"
        if target:
            base = f"rlp-{target.replace('/', '-')}"
        return base + rlp_cpu_series_suffix(rlp_cpu, rlp_cpu_max)
    if target:
        return f"{runner}-{target.replace('/', '-')}"
    return runner


def default_output_path(
    runner: str,
    n: int,
    *,
    benchmark: str = "agent",
    target: str | None = None,
    rlp_cpu: float | None = None,
    rlp_cpu_max: float | None = None,
) -> Path:
    """Path like ``data/agent/rlp/concurrency_<ts>_n10.jsonl``."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    series = result_series_name(
        runner,
        target,
        rlp_cpu=rlp_cpu,
        rlp_cpu_max=rlp_cpu_max,
    )
    base = ROOT / "data" / benchmark / series
    return base / f"concurrency_{stamp}_n{n}.jsonl"
