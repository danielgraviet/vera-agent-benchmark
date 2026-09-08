"""Single-agent workload entrypoint for the Vera agent benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vera agent benchmark workload")
    parser.add_argument(
        "--n",
        type=int,
        default=10,
        help="Work volume (search/AST breadth and pytest case scale)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="repo-agent-v3",
        help="Workload label (repo-agent-v3)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Fixed random seed for workspace generation",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="json",
        choices=["json"],
        help="Output format",
    )
    return parser.parse_args()


def compute_checksum(*parts: object) -> str:
    hasher = hashlib.sha256()
    for part in parts:
        hasher.update(json.dumps(part, sort_keys=True).encode("utf-8"))
    return hasher.hexdigest()


def _run_v3(args: argparse.Namespace) -> None:
    from workload.coding_loop import run_coding_loop

    tmp = tempfile.TemporaryDirectory(prefix="vera-agent-v3-")
    workspace = Path(tmp.name) / "project"
    workspace.mkdir()
    start = time.perf_counter()
    try:
        steps = run_coding_loop(workspace, n=args.n, seed=args.seed)
        duration_ms = int((time.perf_counter() - start) * 1000)
        checksum = compute_checksum(
            steps["seed"],
            steps["search"],
            steps["ast"],
            steps["edit"],
            steps["verify"],
        )
        print(
            json.dumps(
                {
                    "task": args.task,
                    "iterations": args.n,
                    "duration_ms": duration_ms,
                    "checksum": checksum,
                }
            )
        )
    finally:
        tmp.cleanup()


def main() -> None:
    args = parse_args()
    _run_v3(args)


if __name__ == "__main__":
    main()
