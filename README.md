# vera-agent-benchmark

Concurrency harness for a synthetic coding-agent workload. Each sandbox runs a
deterministic search → AST → edit → pytest loop (`workload/`); the host CLI
ramps concurrency and records latency / throughput to JSONL.

## Layout

| Path | Role |
|---|---|
| `main.py` | CLI entrypoint |
| `workload/` | In-sandbox agent workload |
| `harness/` | Runners, paths, reporting |
| `Dockerfile` | Image for registry boots (`agent-benchmark:v3`) |

## Prerequisites

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/)
- Credentials for the backend you use (Daytona and/or RLP)

```bash
uv sync --frozen
cp .env.example .env   # then fill in keys
```

## Runners

| `--runner` | Backend |
|---|---|
| `daytona` | Daytona container sandboxes |
| `daytona-vm` | Daytona Linux VMs (cold disk snapshot) |
| `daytona-vm-hot` | Daytona Linux VMs (memory / warm snapshot) |
| `rlp` | RLP sandboxes via `rlp-sdk` |

## Environment

See `.env.example`. Minimum:

- **Daytona:** `DAYTONA_API_KEY` (and any other vars your Daytona SDK expects)
- **RLP:** `RLP_API_KEY` (optional `RLP_API_URL`); optional CLI `--target` / `--toolbox-url`

## Quick start

```bash
# Daytona
uv run main.py --runner daytona --levels 1 8 --n 20

# RLP (uses registry image agent-benchmark:v3 by default)
uv run main.py --runner rlp --levels 1 8 --n 20

# Override boot image / snapshot
uv run main.py --runner rlp --snapshot agent-benchmark:v3 --levels 1 8
```

Useful flags: `--n` (work volume), `--seed`, `--levels` (concurrency ladder),
`--episodes-per-sandbox` / `-E`, `--exec-timeout`, `--output`.

## Docker image

```bash
docker build -t agent-benchmark:v3 .
# tag/push to whatever registry your RLP cell can pull
```

The image entrypoint is `python -m workload.agent`. `pytest` is a dependency
because the in-sandbox verify step runs it (not for host unit tests).

## Outputs

Runs write under `data/<benchmark>/<series>/concurrency_<ts>_n<N>.jsonl`
(plus a sibling `.meta.json`). Those paths are gitignored — do not commit or
share raw result files if they contain hostnames or internal env probe data.

## Tests

Agent workload regression suite (golden checksums):

```bash
uv run python -m pytest tests/ -v
```

If a refactor changes behavior, checksum assertions in
`tests/test_coding_loop.py` / `tests/golden_agent.json` will fail. Update
goldens only when the change is intentional.

## Notes for integrators

- RLP boots use `--snapshot` / the benchmark `registry_image` (default
  `agent-benchmark:v3`) passed straight through to create — no native snapshot
  lookup in this repo.
