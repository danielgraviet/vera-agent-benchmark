"""Agent benchmark registry and shared container/sandbox contract."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkSpec:
    """Describes one workload for harness runners."""

    id: str
    task_name: str
    artifact_name: str
    module: str
    docker_memory: str = "1g"
    registry_image: str = ""
    pythonpath_extra: str | None = None

    def agent_argv(self, n: int, seed: int) -> list[str]:
        return ["--n", str(n), "--seed", str(seed), "--task", self.task_name]

    def agent_command(self, *, python: str = "python") -> str:
        return f"{python} -m {self.module}"

    def run_env(self, app_dir: str) -> dict[str, str]:
        env = {
            "PATH": f"{app_dir}/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "VIRTUAL_ENV": f"{app_dir}/.venv",
            "PYTHONHASHSEED": "0",
        }
        if self.pythonpath_extra:
            env["PYTHONPATH"] = f"{app_dir}/{self.pythonpath_extra}"
        return env

    def memory_gib(self) -> int:
        """Parse ``docker_memory`` (e.g. ``1g``, ``512m``) into whole GiB (>= 1)."""
        raw = (self.docker_memory or "1g").strip().lower()
        if raw.endswith("gi"):
            return max(1, int(float(raw[:-2])))
        if raw.endswith("g"):
            return max(1, int(float(raw[:-1])))
        if raw.endswith("mi"):
            return max(1, int((float(raw[:-2]) + 1023) // 1024))
        if raw.endswith("m"):
            return max(1, int((float(raw[:-1]) + 1023) // 1024))
        return max(1, int(float(raw)))

    def artifact_for_target(self, target: str | None = None) -> str:
        if not target:
            return self.artifact_name
        return f"{self.artifact_name}-{target.replace('/', '-')}"

    def boot_image_for_rlp(self, target: str | None = None) -> str:
        """Registry image when set; otherwise a named artifact for the target."""
        return self.registry_image or self.artifact_for_target(target)


AGENT = BenchmarkSpec(
    id="agent",
    task_name="repo-agent-v3",
    artifact_name="vera-agent-benchmark",
    module="workload.agent",
    docker_memory="1g",
    registry_image="agent-benchmark:v3",
)

_BENCHMARKS: dict[str, BenchmarkSpec] = {AGENT.id: AGENT}
BENCHMARK_IDS = tuple(_BENCHMARKS)


def get_benchmark(benchmark_id: str) -> BenchmarkSpec:
    try:
        return _BENCHMARKS[benchmark_id]
    except KeyError as exc:
        known = ", ".join(BENCHMARK_IDS)
        raise ValueError(
            f"Unknown benchmark {benchmark_id!r}. Choose from: {known}"
        ) from exc
