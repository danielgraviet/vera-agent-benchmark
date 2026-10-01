# Pre-share review (NVIDIA)

Initial pass over this repo before sharing externally. No secrets were found committed, but there are personal identifiers, internal tribal-knowledge comments, broken doc/script references, and missing packaging polish.

Suggested priority: **P0** = fix before share, **P1** = should fix / clarify, **P2** = nice polish.

---

## P0 — Personal / sensitive / identity

### 1. Personal Docker Hub username hardcoded — DONE
- Was `dtgraviet/vera-agent-benchmark:latest`; now `agent-benchmark:v3`.
- `is_registry_image_ref` updated to treat `name:tag` (no `/`) as a registry ref.

### 2. Git remote and author identity
- Remote: `https://github.com/danielgraviet/vera-agent-benchmark.git`
- Single commit author: `Daniel Thi Graviet <danielthigraviet@gmail.com>`

**Action:** Before sharing, decide whether to:
- Transfer / mirror to an org repo (or send a clean tarball / new remote), and
- Whether commit author email is OK as-is, or re-export with a work identity / squash into a fresh history.

No API keys or `.env` files are in the tree or git history (good). `.gitignore` already covers `.env`, `data/`, `results/`, `*.jsonl`.

### 3. Internal ticket / path references that do not exist here
These point at docs/scripts outside this repo (or never included). They will look broken or leak internal process names:

| Location | Reference |
|---|---|
| `harness/regions.py` module docstring | `tickets/CONTEXT-rlp-arm64-implementation.md`, `tickets/vera-rlp-smoke.md` |
| `harness/regions.py` `require_sdk_field` error | `tickets/vera-rlp-smoke.md`, `../rlp/clients/python` (local eng SDK fork path) |
| `harness/rlp_client_tuning.py` docstring | `RUNBOOK.md` (missing), `rlp-control` host name |
| `harness/rlp_snapshots.py` error text | `uv run scripts/build_rlp_snapshot.py` (script not in repo) |
| `harness/runners/rlp.py` comment | `snapshot_common`, `Dockerfile.*` from another tree |

**Action:** Rewrite comments/errors to be self-contained for this repo, or vendor the needed docs/scripts. Remove references to sibling checkouts and ticket filenames unless those files ship with the share.

---

## P0 — Internal / eng-only wording and infra assumptions

### 4. “Eng:” tribal comments and internal ops shorthand
Scattered informal notes that read as internal Slack leftovers:

- `harness/runners/daytona.py` — “eng: stock VM snaps are not in `us`”; “Eng: VM seed snaps…”
- `harness/regions.py` — “Redswitches credentials from eng”; “eng's SSH tunnel”; “eng's jobs.vm.create…”; “eng's fork”
- `harness/runner_id.py` — “Eng fallback…”
- `harness/rlp_create.py` — “Eng API maps cpu_max…”

**Action:** Rephrase as neutral technical rationale (what/why), without “eng”, ticket names, or onsite SSH assumptions in public-facing comments.

### 5. Hardcoded internal / partner cell endpoints
`harness/regions.py` embeds production/partner RLP URLs and special targets:

- `*.rlp.trydaytona.com` toolbox + API hosts (`arm64-test-1`, `us-phoenix-1`, `redswitches`)
- Local tunnel defaults for `vera` / `digitalocean` (`127.0.0.1:9000`, `127.0.0.1:8088`)
- Target-specific env var names (`VERA_RLP_*`, `PHOENIX_RLP_*`, `REDSWITCHES_*` / `RS_*`, `DO_RLP_*`)

These are not secrets, but they expose internal topology and may confuse or overshare with NVIDIA.

**Action:** Decide with stakeholders whether NVIDIA needs these cells. Options:
- Keep as documented optional targets with a clear “Daytona-internal” note, or
- Strip partner/onsite targets down to a minimal public set (`daytona` + one documented RLP target), driven by env vars only.

### 6. Error message tells users to install a private SDK fork
`require_sdk_field` in `harness/regions.py` instructs:

```text
UV_NO_SYNC=1 uv pip install -e ../rlp/clients/python
```

That path will not exist for NVIDIA and implies a private fork.

**Action:** Document public `rlp-sdk` version requirements, or ship/link a supported install path. Fail with a version/capability message that does not assume a sibling monorepo.

---

## P1 — Incomplete / misleading package surface

### 7. Empty `scripts/` and `tests/` directories
Both exist only as empty shells (local `__pycache__` only). Code still tells users to run `scripts/build_rlp_snapshot.py`. `pytest` is a dependency in `pyproject.toml` but there are no tests.

**Action:** Either add the missing build/test scripts, or remove the empty dirs and drop unused `pytest` from runtime deps (or move it to a `[dependency-groups]` / optional/dev group).

### 8. README is too thin for an external handoff
Current README covers a one-line description and two example commands. Missing for a clean share:

- What this benchmark measures and what “Vera” means in this context
- Required accounts / env vars (`DAYTONA_*`, `RLP_API_KEY`, target-specific vars)
- How to build/push the Docker image and set `registry_image`
- Runner matrix (`daytona`, `daytona-vm`, `daytona-vm-hot`, `rlp`) — README only mentions two
- Prerequisites (`uv`, Python 3.13, network access to the chosen backend)
- What outputs look like (`data/…/*.jsonl`, gitignored)
- License / contact / support expectations

**Action:** Expand README (and optionally add `.env.example`) before sharing.

### 9. No LICENSE
There is no `LICENSE` (or license field in `pyproject.toml`).

**Action:** Add an explicit license approved for the NVIDIA share (and matching `pyproject` metadata if desired).

### 10. No `.env.example`
Runners call `load_dotenv(ROOT / ".env")`, but there is no example file listing required keys.

**Action:** Add `.env.example` with placeholder names only (no real values). Document the same in README.

### 11. Broken / missing documentation references
- `RUNBOOK.md` referenced but absent
- Ticket markdown files referenced but absent
- Snapshot build script referenced but absent

**Action:** Add a short runbook for snapshot/image build + first successful run, or delete dangling references.

---

## P1 — Code polish / share-readiness

### 12. SDK monkey-patches and private APIs
- `harness/rlp_client_tuning.py` monkey-patches `rlp.http.HttpClient.__init__` and `Sandbox.wait_until_started`
- `harness/rlp_snapshots.py` uses `client._api.get/delete` (private)

Fragile for external consumers on newer SDK versions; also looks “hacky” in a partner review.

**Action:** Call out clearly in README as intentional client-side tuning; ideally gate behind a flag or document supported `rlp-sdk` versions. Prefer public SDK APIs where possible.

### 13. Personal / machine metadata in run output
`main.py` records `socket.gethostname()` into JSONL meta for RLP runs. Fine locally; if results are ever shared, hostnames can identify laptops/employees.

**Action:** Document that `data/` must not be shared, or omit/redact `client_host` by default for external builds.

### 14. Verbose `print` logging
~25 `print(...)` call sites across harness/runners (client config, probes, warnings). Fine for a CLI harness; slightly noisy for a polished partner drop.

**Action:** Optional — switch to `logging` with a `--verbose` flag. Not blocking if README sets expectations.

### 15. `pyproject.toml` hygiene
- `pytest` listed as a main dependency with no tests
- No `license`, `authors`, or project URLs
- Description is minimal

**Action:** Tighten metadata for an external package feel; move test deps to a dev group.

---

## P2 — Smaller cleanups

### 16. README / CLI mismatch
README: “two runners: `daytona` and `rlp`”. Code also supports `daytona-vm` and `daytona-vm-hot`.

### 17. Default concurrency ladder looks internal
`main.py` defaults `--levels` to `[1, 8, 22, 44, 88, 176]` — fine technically, but undocumented; NVIDIA may not know why those numbers.

### 18. Informal benchmark task naming
`repo-agent-v3` / “Coding-agent v3” in specs — versioning suggests prior internal iterations. Harmless, but could be renamed to a stable public label if desired.

### 19. Local empty `__pycache__` under `scripts/` and `tests/`
Not tracked by git; delete empty dirs so the tree does not look unfinished when browsing the working copy.

### 20. Confirm share channel
Clarify whether NVIDIA gets: this GitHub repo as-is, a private org fork, a zip without `.git`, or a scrubbed history. That choice drives how hard to scrub author email / remote (item 2).

---

## What already looks good

- No committed credentials, tokens, or `.env` files
- Secrets are env-driven (`RLP_API_KEY`, `VERA_RLP_API_KEY`, etc.) with fail-fast errors
- `.gitignore` excludes `.env`, venvs, caches, `data/`, `results/`, JSONL outputs
- Repo is small and focused (workload + harness + CLI)
- Single clean commit history (easy to re-export if needed)
- Dockerfile is minimal and reproducible via `uv.lock`

---

## Suggested fix order (for the next pass)

1. ~~Neutralize personal Docker image refs (`dtgraviet/…`)~~ → `agent-benchmark:v3`
2. Strip or rewrite ticket / eng / sibling-repo / RUNBOOK references
3. Decide which RLP targets ship externally; document or remove the rest
4. Add LICENSE + `.env.example` + fuller README
5. Remove or fill empty `scripts/` / `tests/`; fix `pytest` dependency placement
6. Decide git remote / author / history strategy for the actual handoff
7. Optional polish: logging, hostname redaction, SDK private-API notes

---

*Generated as an initial review pass only — no code changes applied yet.*
