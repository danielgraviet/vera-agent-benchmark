"""CLI entrypoint: JSON shape + golden checksum."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_agent(*args: str) -> dict:
    import os

    proc = subprocess.run(
        [sys.executable, "-m", "workload.agent", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_cli_n1_seed42_matches_golden(golden: dict) -> None:
    payload = _run_agent("--n", "1", "--seed", "42")
    assert payload["task"] == "repo-agent-v3"
    assert payload["iterations"] == 1
    assert isinstance(payload["duration_ms"], int)
    assert payload["duration_ms"] >= 0
    assert payload["checksum"] == golden["checksums"]["n1_seed42"]


def test_cli_default_task_label(golden: dict) -> None:
    payload = _run_agent("--n", "1", "--seed", "7", "--task", "repo-agent-v3")
    assert payload["task"] == "repo-agent-v3"
    assert payload["checksum"] == golden["checksums"]["n1_seed7"]


def test_cli_checksum_independent_of_duration(golden: dict) -> None:
    """duration_ms is wall time and must not affect checksum."""
    a = _run_agent("--n", "1", "--seed", "42")
    b = _run_agent("--n", "1", "--seed", "42")
    assert a["checksum"] == b["checksum"] == golden["checksums"]["n1_seed42"]
    # durations may differ; that's fine
    assert "duration_ms" in a and "duration_ms" in b
