# vera-agent-benchmark

Small harness for the Vera agent concurrency benchmark.

- one workload: `agent` (`workload/`)
- runners: `daytona`, `daytona-vm`, `daytona-vm-hot`, `rlp`
- no benchmark results or generated JSONL files (gitignored under `data/`)

Layout:

- `main.py` — CLI entrypoint
- `workload/agent.py` — workload inside each sandbox
- `harness/` — runners, output paths, reporting helpers
- `Dockerfile` — image used for registry boots (`agent-benchmark:v3`)

Quick start:

```bash
uv sync --frozen
# Daytona (credentials via DAYTONA_* / .env)
uv run main.py --runner daytona --levels 1 8 --n 20
# RLP (credentials via RLP_API_KEY / .env; optional --target / --toolbox-url)
uv run main.py --runner rlp --levels 1 8 --n 20
```
