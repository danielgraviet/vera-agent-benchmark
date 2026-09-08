"""Agent benchmark registry and shared container contract."""

from __future__ import annotations

from dataclasses import dataclass

from harness.regions import REGISTRY_BOOT_TARGETS


@dataclass(frozen=True)
class BenchmarkSpec:
    """Describes the agent benchmark for harness and image builders."""

    id: str
    task_name: str
    docker_image: str
    artifact_name: str
    module: str
    include_paths: tuple[str, ...]
    pythonpath_extra: str | None = None
    docker_memory: str = "1g"
    description: str = ""
    apt_packages: tuple[str, ...] = ()
    registry_image: str = ""

    def agent_argv(self, n: int, seed: int) -> list[str]:
        return ["--n", str(n), "--seed", str(seed), "--task", self.task_name]

    def run_env(self, app_dir: str) -> dict[str, str]:
        env = {
            "PATH": f"{app_dir}/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "VIRTUAL_ENV": f"{app_dir}/.venv",
            "PYTHONHASHSEED": "0",
        }
        if self.pythonpath_extra:
            env["PYTHONPATH"] = f"{app_dir}/{self.pythonpath_extra}"
        return env

    def agent_command(self, *, python: str = "python") -> str:
        return f"{python} -m {self.module}"

    def memory_gib(self) -> int:
        raw = (self.docker_memory or "1g").strip().lower()
        if raw.endswith("gi"):
            return max(1, int(float(raw[:-2])))
        if raw.endswith("g"):
            return max(1, int(float(raw[:-1])))
        if raw.endswith("mi") or raw.endswith("m"):
            mib = float(raw[:-2] if raw.endswith("mi") else raw[:-1])
            return max(1, int((mib + 1023) // 1024))
        return max(1, int(float(raw)))

    def artifact_for_target(self, target: str | None = None) -> str:
        if not target:
            return self.artifact_name
        safe = target.replace("/", "-")
        return f"{self.artifact_name}-{safe}"

    def boot_image_for_rlp(self, target: str | None = None) -> str:
        if target in REGISTRY_BOOT_TARGETS:
            if not self.registry_image:
                raise ValueError(
                    f"Benchmark {self.id!r} has no registry_image for target {target!r}"
                )
            return self.registry_image
        return self.artifact_for_target(target)


AGENT = BenchmarkSpec(
    id="agent",
    task_name="repo-agent-v3",
    docker_image="vera-agent-benchmark",
    artifact_name="vera-agent-benchmark",
    module="workload.agent",
    include_paths=("pyproject.toml", "uv.lock", "workload"),
    pythonpath_extra=None,
    docker_memory="1g",
    description=(
        "Coding-agent v3: seed broken package -> search -> AST -> oracle edit -> "
        "heavy pytest (no SQL); deterministic --n/--seed checksum"
    ),
    registry_image="dtgraviet/vera-agent-benchmark:latest",
)

BENCHMARKS: dict[str, BenchmarkSpec] = {AGENT.id: AGENT}

BENCHMARK_IDS = tuple(BENCHMARKS)
SNAPSHOT_BENCHMARK_IDS = BENCHMARK_IDS


def get_benchmark(benchmark_id: str) -> BenchmarkSpec:
    try:
        return BENCHMARKS[benchmark_id]
    except KeyError as exc:
        known = ", ".join(BENCHMARK_IDS)
        raise ValueError(f"Unknown benchmark {benchmark_id!r}. Choose from: {known}") from exc
