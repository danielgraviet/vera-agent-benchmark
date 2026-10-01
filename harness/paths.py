"""Default JSONL output paths under ``data/<benchmark>/<series>/``."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _fmt_cpu(value: float) -> str:
    """Format a CPU value for folder names (``0.5`` → ``0p5``)."""
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return text.replace(".", "p")


def _safe_segment(value: str) -> str:
    return value.replace("/", "-")


def _rlp_cpu_series_suffix(cpu: float | None, cpu_max: float | None = None) -> str:
    """Suffix for non-default RLP CPU settings (e.g. ``-c0p5-max1``)."""
    parts: list[str] = []
    if cpu is not None and abs(float(cpu) - 1.0) >= 1e-9:
        parts.append("c" + _fmt_cpu(cpu))
    if cpu_max is not None:
        parts.append("max" + _fmt_cpu(cpu_max))
    return ("-" + "-".join(parts)) if parts else ""


def _result_series_name(
    runner: str,
    target: str | None = None,
    *,
    rlp_cpu: float | None = None,
    rlp_cpu_max: float | None = None,
) -> str:
    """Map CLI runner + optional target to a results folder name."""
    if runner == "rlp":
        base = f"rlp-{_safe_segment(target)}" if target else "rlp"
        return base + _rlp_cpu_series_suffix(rlp_cpu, rlp_cpu_max)
    if target:
        return f"{runner}-{_safe_segment(target)}"
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
    series = _result_series_name(
        runner,
        target,
        rlp_cpu=rlp_cpu,
        rlp_cpu_max=rlp_cpu_max,
    )
    return ROOT / "data" / benchmark / series / f"concurrency_{stamp}_n{n}.jsonl"
