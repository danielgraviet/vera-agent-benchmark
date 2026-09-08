"""Shared concurrency harness helpers."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Self, TextIO

# One concurrent worker → one or more episode records (sandbox reuse).
RunWorker = Callable[[int, int], list[dict[str, Any]]]
# Back-compat alias for single-shot runners.
RunOne = Callable[[int, int], dict[str, Any]]


class JsonlWriter:
    """Append-only JSON Lines writer that flushes after every record."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fp: TextIO | None = None

    def __enter__(self) -> Self:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self._path.open("w", encoding="utf-8")
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def write(self, record: dict[str, Any]) -> None:
        if self._fp is None:
            raise RuntimeError("JsonlWriter is not open")
        self._fp.write(json.dumps(record, separators=(",", ":")) + "\n")
        self._fp.flush()


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def apply_workload_payload(record: dict[str, Any], payload: dict[str, Any]) -> None:
    """Copy stable fields from in-sandbox JSON onto a harness run record."""
    for key in ("checksum", "duration_ms", "eval_task_id"):
        if payload.get(key) is not None:
            record[key] = payload[key]


def summarize(
    records: list[dict[str, Any]],
    wall_time_s: float,
    *,
    max_distinct_checksums: int = 1,
) -> dict[str, Any]:
    latencies = [float(r["latency_ms"]) for r in records if "latency_ms" in r]
    warm_latencies = [
        float(r["latency_ms"])
        for r in records
        if "latency_ms" in r and r.get("cold") is False
    ]
    durations = [
        float(r["duration_ms"])
        for r in records
        if r.get("duration_ms") is not None
    ]
    checksums = {r["checksum"] for r in records if r.get("checksum")}
    failures = [r for r in records if r.get("exit_code", 0) != 0]
    runner_ids = {str(r["runner_id"]) for r in records if r.get("runner_id")}

    summary: dict[str, Any] = {
        "runs": len(records),
        "failures": len(failures),
        "distinct_checksums": len(checksums),
        "checksum_ok": len(checksums) <= max_distinct_checksums and not failures,
        "p50_ms": round(percentile(latencies, 50), 1),
        "p95_ms": round(percentile(latencies, 95), 1),
        "p99_ms": round(percentile(latencies, 99), 1),
        "max_ms": round(max(latencies), 1) if latencies else 0,
        "throughput_per_sec": (
            round((len(records) - len(failures)) / wall_time_s, 2)
            if wall_time_s > 0
            else 0
        ),
        "attempt_throughput_per_sec": (
            round(len(records) / wall_time_s, 2) if wall_time_s > 0 else 0
        ),
    }
    if durations:
        summary["p50_duration_ms"] = round(percentile(durations, 50), 1)
        summary["p99_duration_ms"] = round(percentile(durations, 99), 1)
        summary["max_duration_ms"] = round(max(durations), 1)
    if warm_latencies:
        summary["p50_warm_ms"] = round(percentile(warm_latencies, 50), 1)
        summary["p99_warm_ms"] = round(percentile(warm_latencies, 99), 1)
    if runner_ids:
        summary["distinct_runners"] = len(runner_ids)
    return summary


def run_level(
    concurrency: int,
    n: int,
    seed: int,
    run_worker: RunWorker,
    *,
    job_seed_mod: int = 1,
) -> Iterator[dict[str, Any]]:
    """Yield each episode result as soon as that worker finishes.

    ``job_seed_mod > 1`` rotates the seed per concurrent job
    (``seed + i % job_seed_mod``). Default 1: every job uses the same seed.
    """
    mod = max(1, job_seed_mod)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(run_worker, n, seed + (i % mod)) for i in range(concurrency)
        ]
        for future in as_completed(futures):
            for record in future.result():
                yield record


def run_suite(
    *,
    levels: list[int],
    n: int,
    seed: int,
    output: Path,
    run_worker: RunWorker,
    meta: dict[str, Any] | None = None,
    job_seed_mod: int = 1,
) -> None:
    max_checksums = max(1, job_seed_mod)
    with JsonlWriter(output) as writer:
        if meta:
            writer.write({"type": "meta", **meta})
        for level in levels:
            start = time.monotonic()
            records: list[dict[str, Any]] = []

            for record in run_level(
                level, n, seed, run_worker, job_seed_mod=job_seed_mod
            ):
                writer.write({"type": "run", "concurrency": level, **record})
                records.append(record)

            wall_time_s = time.monotonic() - start
            summary = summarize(
                records, wall_time_s, max_distinct_checksums=max_checksums
            )
            writer.write({"type": "summary", "concurrency": level, **summary})
            print(json.dumps({"concurrency": level, **summary}))


def run_hold_suite(
    *,
    levels: list[int],
    n: int,
    seed: int,
    output: Path,
    runner: Any,
    meta: dict[str, Any] | None = None,
    job_seed_mod: int = 1,
) -> None:
    """Pre-create a fleet of C, barrier, exec, then delete.

    ``throughput_per_sec`` is completed episodes / exec-wave wall (chip packing).
    ``attempt_throughput_per_sec`` keeps the raw attempt rate for auditability.
    ``throughput_including_create`` keeps the product number that includes
    sandbox boot. Create/delete churn is isolated from episode ``duration_ms``.
    """
    episodes = int(getattr(runner, "_episodes_per_sandbox", 1))
    if episodes < 1:
        raise ValueError("episodes_per_sandbox must be >= 1")
    max_checksums = max(1, job_seed_mod)
    spec_id = getattr(getattr(runner, "_spec", None), "id", None)
    target = getattr(runner, "_target", None)

    def _write(writer: JsonlWriter, level: int, record: dict[str, Any]) -> dict[str, Any]:
        writer.write({"type": "run", "concurrency": level, **record})
        return record

    with JsonlWriter(output) as writer:
        if meta:
            writer.write({"type": "meta", **meta})
        for level in levels:
            create_start = time.monotonic()
            fleet: list[Any] = []
            records: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=level) as pool:
                futures = [pool.submit(runner.create_sandbox) for _ in range(level)]
                for future in as_completed(futures):
                    try:
                        fleet.append(future.result())
                    except Exception as exc:  # noqa: BLE001
                        records.append(
                            _write(
                                writer,
                                level,
                                {
                                    "latency_ms": (time.monotonic() - create_start)
                                    * 1000,
                                    "exit_code": -1,
                                    "error": f"{type(exc).__name__}: {exc}",
                                    "target": target,
                                    "arch": getattr(runner, "_arch", "unspecified"),
                                    "benchmark": spec_id,
                                    "episode_idx": 0,
                                    "cold": True,
                                    "fleet_hold": True,
                                },
                            )
                        )
            create_wall_s = time.monotonic() - create_start

            exec_start = time.monotonic()
            if fleet:
                with ThreadPoolExecutor(max_workers=len(fleet)) as pool:
                    futures = [
                        pool.submit(
                            runner.exec_on_sandbox,
                            sandbox,
                            n,
                            seed,
                            episodes,
                            cold_first=False,
                        )
                        for sandbox in fleet
                    ]
                    for future in as_completed(futures):
                        for record in future.result():
                            records.append(_write(writer, level, record))
            exec_wall_s = time.monotonic() - exec_start

            delete_start = time.monotonic()
            if fleet:
                with ThreadPoolExecutor(max_workers=len(fleet)) as pool:
                    futs = [
                        pool.submit(runner.delete_sandbox, sandbox) for sandbox in fleet
                    ]
                    for fut in as_completed(futs):
                        try:
                            fut.result()
                        except Exception:  # noqa: BLE001, S110
                            pass
            delete_wall_s = time.monotonic() - delete_start

            summary = summarize(
                records, exec_wall_s, max_distinct_checksums=max_checksums
            )
            summary["create_wall_s"] = round(create_wall_s, 3)
            summary["exec_wall_s"] = round(exec_wall_s, 3)
            summary["delete_wall_s"] = round(delete_wall_s, 3)
            if exec_wall_s < 0.001 or not fleet:
                summary["throughput_per_sec"] = 0.0
                summary["attempt_throughput_per_sec"] = 0.0
            include_create = create_wall_s + exec_wall_s
            summary["throughput_including_create"] = (
                round(len(records) / include_create, 2) if include_create > 0 else 0
            )
            writer.write({"type": "summary", "concurrency": level, **summary})
            print(
                json.dumps(
                    {
                        "concurrency": level,
                        "hold_then_exec": True,
                        "benchmark": spec_id,
                        "target": target,
                        **summary,
                    }
                )
            )
