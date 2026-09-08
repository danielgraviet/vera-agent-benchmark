# vera-agent-benchmark

This repository contains the code for the Vera agent benchmark only.

It is meant to be a small, shareable harness repo:

- one workload: `agent`
- two runners: `daytona` and `rlp`
- no benchmark results or generated JSONL files

Included:

- the agent workload entrypoint under `workload/`
- the concurrency harness under `harness/`
- daytona and rlp runner support

Layout:

- `main.py` is the CLI entrypoint
- `workload/agent.py` runs the benchmark workload inside each sandbox
- `harness/` contains runner setup, output paths, and reporting helpers

Quick start:

```bash
uv sync --frozen
uv run main.py --runner daytona --levels 1 8 --n 20
uv run main.py --runner rlp --target arm64-test-1 --levels 1 8
```
