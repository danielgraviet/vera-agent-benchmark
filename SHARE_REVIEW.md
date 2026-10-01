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
Region routing was gutted for the share.

---

## P1 — Incomplete / misleading package surface

### 7. Empty `scripts/` / `tests/` / pytest — DONE
`tests/` filled with agent golden-checksum suite. Keep `pytest` in
`pyproject.toml` (workload + host tests).

### 8. README — DONE
Expanded with layout, runners, env, Docker build, outputs, integrator notes.

### 9. No LICENSE — OPEN
There is no `LICENSE` (or license field in `pyproject.toml`).

**Action:** Add an explicit license approved for the NVIDIA share.

### 10. `.env.example` — DONE
Added with placeholder Daytona / RLP / tuning vars.

### 11. Broken / missing documentation references — DONE

---

## P1 — Code polish / share-readiness

### 12. SDK monkey-patches and private APIs — DONE (documented)
Called out in README under “Notes for integrators”.

### 13. Personal / machine metadata in run output — PARTIALLY DONE
README warns not to share raw `data/` JSONL. Optional: omit `client_host` in code.

### 14. Verbose `print` logging — OPEN (optional)

### 15. `pyproject.toml` hygiene — OPEN
- No `license`, `authors`, or project URLs (pytest stays — see #7)

---

## P2 — Smaller cleanups

### 16. README / CLI mismatch — DONE

### 17. Default concurrency ladder — OPEN
`main.py` defaults `--levels` to `[1, 8, 22, 44, 88, 176]` — undocumented.

### 18. Informal benchmark task naming — OPEN

### 19. Empty `__pycache__` under scripts/tests — DONE

### 20. Confirm share channel — OPEN

---

## Suggested remaining fix order

1. Add LICENSE (needs a chosen license)
2. Decide git remote / author / history strategy for the handoff
3. Optional: omit `client_host` from meta; quieter logging; `pyproject` metadata

---

*Updated after README / .env.example pass.*
