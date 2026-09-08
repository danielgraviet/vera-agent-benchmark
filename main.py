"""Concurrency harness CLI for the Vera agent benchmark."""

from __future__ import annotations

import argparse
import json
import socket
from pathlib import Path

from harness.benchmarks import BENCHMARK_IDS, get_benchmark
from harness.common import run_hold_suite, run_suite
from harness.paths import default_output_path
from harness.rlp_client_tuning import settings as rlp_client_tuning_settings
from harness.runners import (
    DAYTONA_FAMILY,
    RUNNERS,
    build_runner,
    probe_runner_env,
    runner_as_worker,
)
from harness.runners.daytona import default_daytona_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Vera agent benchmark harness")
    parser.add_argument(
        "--benchmark",
        default="agent",
        choices=BENCHMARK_IDS,
        help="Workload package (agent)",
    )
    parser.add_argument(
        "--runner",
        required=True,
        choices=RUNNERS,
        help="Worker backend / result folder under data/<benchmark>/",
    )
    parser.add_argument("--levels", type=int, nargs="+", default=[1, 8, 22, 44, 88, 176])
    parser.add_argument("--n", type=int, default=20, help="Work volume")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--episodes-per-sandbox",
        "-E",
        type=int,
        default=1,
        help="Episodes to exec per sandbox before delete (daytona/daytona-vm/rlp)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Override JSONL path",
    )
    parser.add_argument(
        "--snapshot",
        type=str,
        default=None,
        help="Override snapshot/template name, or a registry image ref for RLP",
    )
    parser.add_argument(
        "--exec-timeout",
        type=int,
        default=600,
        help="Seconds allowed for process.exec inside each sandbox",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        help="Region/target for daytona/daytona-vm/daytona-vm-hot/rlp",
    )
    parser.add_argument(
        "--toolbox-url",
        type=str,
        default=None,
        help="Override RLP toolbox proxy URL (defaults from --target map or env)",
    )
    parser.add_argument(
        "--rlp-cpu",
        type=float,
        default=1.0,
        help="RLP create Resources.cpu guarantee (default 1)",
    )
    parser.add_argument(
        "--rlp-cpu-max",
        type=float,
        default=None,
        help="RLP Resources.cpu_max burst cap in vCPUs (e.g. 1)",
    )
    parser.add_argument(
        "--rlp-memory",
        type=float,
        default=None,
        help="RLP Resources.memory GiB guarantee",
    )
    parser.add_argument(
        "--rlp-memory-max",
        type=float,
        default=None,
        help="RLP Resources.memory_max GiB burst cap (e.g. 4)",
    )
    parser.add_argument(
        "--rlp-disk",
        type=float,
        default=None,
        help="RLP Resources.disk GiB (default: max(2, memory))",
    )
    parser.add_argument(
        "--hold-then-exec",
        action="store_true",
        help="RLP only: pre-create a fleet, then exec all sandboxes, then delete",
    )
    args = parser.parse_args()

    if args.toolbox_url and args.runner != "rlp":
        parser.error("--toolbox-url is only valid with --runner rlp")
    if args.target and args.runner not in (*DAYTONA_FAMILY, "rlp"):
        parser.error("--target is only valid with --runner daytona/daytona-vm/daytona-vm-hot/rlp")
    if args.rlp_cpu != 1.0 and args.runner != "rlp":
        parser.error("--rlp-cpu is only valid with --runner rlp")
    if args.rlp_cpu <= 0:
        parser.error("--rlp-cpu must be > 0")
    burst_flags = (
        args.rlp_cpu_max is not None
        or args.rlp_memory is not None
        or args.rlp_memory_max is not None
        or args.rlp_disk is not None
    )
    if burst_flags and args.runner != "rlp":
        parser.error("--rlp-cpu-max / --rlp-memory / --rlp-memory-max / --rlp-disk are only valid with --runner rlp")
    if args.rlp_cpu_max is not None and args.rlp_cpu_max < args.rlp_cpu:
        parser.error("--rlp-cpu-max must be >= --rlp-cpu")
    if args.episodes_per_sandbox < 1:
        parser.error("--episodes-per-sandbox must be >= 1")
    if args.episodes_per_sandbox > 1 and args.runner not in (*DAYTONA_FAMILY, "rlp"):
        parser.error("--episodes-per-sandbox > 1 is only supported with daytona/daytona-vm/daytona-vm-hot or rlp")
    if args.hold_then_exec and args.runner != "rlp":
        parser.error("--hold-then-exec is only valid with --runner rlp")

    spec = get_benchmark(args.benchmark)
    if args.snapshot:
        artifact = args.snapshot
    elif args.runner == "rlp":
        artifact = spec.boot_image_for_rlp(args.target)
    elif args.runner in DAYTONA_FAMILY:
        if args.runner == "daytona-vm-hot":
            kind, boot = "vm", "hot"
        elif args.runner == "daytona-vm":
            kind, boot = "vm", "cold"
        else:
            kind, boot = "container", "cold"
        if args.target:
            base = spec.artifact_for_target(args.target)
            artifact = f"{base}-hot" if boot == "hot" else base
        else:
            artifact = default_daytona_snapshot(spec, kind, vm_boot=boot)
    else:
        artifact = spec.artifact_name

    output = (
        Path(args.output)
        if args.output
        else default_output_path(
            args.runner,
            args.n,
            benchmark=args.benchmark,
            target=args.target,
            rlp_cpu=args.rlp_cpu if args.runner == "rlp" else None,
            rlp_cpu_max=args.rlp_cpu_max if args.runner == "rlp" else None,
        )
    )
    print(
        f"benchmark={args.benchmark} runner={args.runner} target={args.target!r} "
        f"artifact={artifact!r} episodes_per_sandbox={args.episodes_per_sandbox} "
        f"rlp_cpu={args.rlp_cpu!r} rlp_cpu_max={args.rlp_cpu_max!r} "
        f"rlp_memory={args.rlp_memory!r} rlp_memory_max={args.rlp_memory_max!r} "
        f"rlp_disk={args.rlp_disk!r} hold_then_exec={args.hold_then_exec} "
        f"output={output}"
    )

    meta = {
        "benchmark": args.benchmark,
        "runner": args.runner,
        "target": args.target,
        "artifact": artifact,
        "seed": args.seed,
        "n": args.n,
        "episodes_per_sandbox": args.episodes_per_sandbox,
        "rlp_cpu": args.rlp_cpu if args.runner == "rlp" else None,
        "rlp_cpu_max": args.rlp_cpu_max if args.runner == "rlp" else None,
        "rlp_memory": args.rlp_memory if args.runner == "rlp" else None,
        "rlp_memory_max": args.rlp_memory_max if args.runner == "rlp" else None,
        "rlp_disk": args.rlp_disk if args.runner == "rlp" else None,
        "hold_then_exec": bool(args.hold_then_exec),
    }
    if args.runner == "rlp":
        meta["rlp_client_tuning"] = rlp_client_tuning_settings()
        meta["client_host"] = socket.gethostname()

    runner = build_runner(args)
    meta["env"] = probe_runner_env(runner, runner_name=args.runner)
    print(f"env={json.dumps(meta['env'], separators=(',', ':'))}")

    if args.hold_then_exec:
        run_hold_suite(
            levels=args.levels,
            n=args.n,
            seed=args.seed,
            output=output,
            runner=runner,
            meta=meta,
            job_seed_mod=1,
        )
        return

    run_suite(
        levels=args.levels,
        n=args.n,
        seed=args.seed,
        output=output,
        run_worker=runner_as_worker(runner, args),
        meta=meta,
        job_seed_mod=1,
    )


if __name__ == "__main__":
    main()
