# Pre-share review (NVIDIA)

Initial pass over this repo before sharing externally. Updated as cleanup proceeds.

Suggested priority: **P0** = fix before share, **P1** = should fix / clarify, **P2** = nice polish.

---

## P0 — Personal / sensitive / identity

### 1. Personal Docker Hub username hardcoded — DONE
- Was `dtgraviet/vera-agent-benchmark:latest`; now `agent-benchmark:v3`.
- `is_registry_image_ref` updated to treat `name:tag` (no `/`) as a registry ref.

### 2. Git remote and author identity — OPEN
- Remote: `https://github.com/danielgraviet/vera-agent-benchmark.git`
- Single commit author: `Daniel Thi Graviet <danielthigraviet@gmail.com>`

**Action:** Before sharing, decide whether to:
- Transfer / mirror to an org repo (or send a clean tarball / new remote), and
- Whether commit author email is OK as-is, or re-export with a work identity / squash into a fresh history.

No API keys or `.env` files are in the tree or git history (good). `.gitignore` already covers `.env`, `data/`, `results/`, `*.jsonl`.

### 3–6. Ticket paths / eng wording / partner cell routing / private SDK fork — DONE
Region routing was gutted for the share:

- `harness/regions.py` is now a thin `--target` / `--toolbox-url` passthrough
- Removed hardcoded `*.rlp.trydaytona.com` URLs, vera/phoenix/redswitches/digitalocean special cases, ARM64/vera cpu maps, arch probe, `require_sdk_field` eng-fork install path
- Scrubbed ticket / RUNBOOK / “eng:” comments from harness modules
- RLP always prefers `registry_image` (`agent-benchmark:v3`)
- Empty `scripts/` and `tests/` directories removed; dangling `build_rlp_snapshot.py` reference removed
- README updated for the simplified surface

---

## P1 — Incomplete / misleading package surface

### 7. Empty `scripts/` and `tests/` — MOSTLY DONE
Dirs removed. `pytest` is still a main dependency in `pyproject.toml` with no tests.

**Action:** Drop unused `pytest` from runtime deps (or move to a dev group).

### 8. README — PARTIALLY DONE
Runner matrix and basic RLP env notes updated. Still thin on:

- What this benchmark measures / what “Vera” means
- Full env var list and image build/push steps
- Output layout detail
- License / contact

**Action:** Expand further if NVIDIA needs a self-serve runbook.

### 9. No LICENSE — OPEN
There is no `LICENSE` (or license field in `pyproject.toml`).

**Action:** Add an explicit license approved for the NVIDIA share.

### 10. No `.env.example` — OPEN
Runners call `load_dotenv(ROOT / ".env")`, but there is no example file.

**Action:** Add `.env.example` with placeholder names only.

### 11. Broken / missing documentation references — DONE
Dangling RUNBOOK / ticket / snapshot-script refs removed from code paths.

---

## P1 — Code polish / share-readiness

### 12. SDK monkey-patches and private APIs — OPEN
- `harness/rlp_client_tuning.py` monkey-patches httpx pool + wait polling
- `harness/rlp_snapshots.py` uses `client._api.get/delete`

**Action:** Call out in README; document supported `rlp-sdk` versions.

### 13. Personal / machine metadata in run output — OPEN
`main.py` records `socket.gethostname()` into JSONL meta for RLP runs.

**Action:** Document that `data/` must not be shared, or omit/redact `client_host`.

### 14. Verbose `print` logging — OPEN (optional)
Fine for a CLI harness; optional switch to `logging` + `--verbose`.

### 15. `pyproject.toml` hygiene — OPEN
- `pytest` listed as a main dependency with no tests
- No `license`, `authors`, or project URLs

---

## P2 — Smaller cleanups

### 16. README / CLI mismatch — DONE
README now lists `daytona`, `daytona-vm`, `daytona-vm-hot`, `rlp`.

### 17. Default concurrency ladder — OPEN
`main.py` defaults `--levels` to `[1, 8, 22, 44, 88, 176]` — undocumented.

### 18. Informal benchmark task naming — OPEN
`repo-agent-v3` / “Coding-agent v3” — harmless; rename only if a public label is preferred.

### 19. Empty `__pycache__` under scripts/tests — DONE
Dirs removed.

### 20. Confirm share channel — OPEN
Clarify whether NVIDIA gets this GitHub repo, a private org fork, a zip without `.git`, or scrubbed history.

---

## What already looks good

- No committed credentials, tokens, or `.env` files
- Secrets are env-driven with fail-fast errors
- `.gitignore` excludes `.env`, venvs, caches, `data/`, `results/`, JSONL outputs
- Repo is small and focused (workload + harness + CLI)
- Single clean commit history (easy to re-export if needed)
- Dockerfile is minimal and reproducible via `uv.lock`
- Region / partner-cell bootstrap code removed for share

---

## Suggested remaining fix order

1. Add LICENSE + `.env.example`
2. Drop or relocate unused `pytest` dependency
3. Decide git remote / author / history strategy for the handoff
4. Optional: hostname redaction, SDK private-API notes, fuller README

---

*Updated after region-routing simplification pass.*
