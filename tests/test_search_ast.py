"""Search + AST passes: digests and counts must stay stable."""

from __future__ import annotations

from pathlib import Path

from workload.coding_loop import ast_repo, search_repo, seed_workspace


def test_search_and_ast_match_golden(workspace: Path, golden: dict) -> None:
    seed_workspace(workspace, n=1, seed=42)
    steps = golden["n1_seed42_steps"]
    assert search_repo(workspace, n=1) == steps["search"]
    assert ast_repo(workspace, n=1) == steps["ast"]


def test_search_and_ast_deterministic_across_calls(workspace: Path) -> None:
    seed_workspace(workspace, n=2, seed=42)
    assert search_repo(workspace, n=2) == search_repo(workspace, n=2)
    assert ast_repo(workspace, n=2) == ast_repo(workspace, n=2)


def test_search_scales_with_n_iterations(workspace: Path) -> None:
    seed_workspace(workspace, n=1, seed=42)
    one = search_repo(workspace, n=1)
    two = search_repo(workspace, n=2)
    assert two["iterations"] == 2
    assert two["total_matches"] == one["total_matches"] * 2
    assert two["digest"] != one["digest"]


def test_ast_scales_with_n_iterations(workspace: Path) -> None:
    seed_workspace(workspace, n=1, seed=42)
    one = ast_repo(workspace, n=1)
    two = ast_repo(workspace, n=2)
    assert two["total_functions"] == one["total_functions"] * 2
    assert two["total_classes"] == one["total_classes"] * 2
    assert two["digest"] != one["digest"]


def test_different_seed_changes_generated_sources(
    workspace: Path, tmp_path: Path
) -> None:
    other = tmp_path / "other"
    other.mkdir()
    seed_workspace(workspace, n=1, seed=42)
    seed_workspace(other, n=1, seed=7)
    assert (workspace / "app" / "util_000.py").read_text(
        encoding="utf-8"
    ) != (other / "app" / "util_000.py").read_text(encoding="utf-8")
    # Structural regex search is identical for equal module counts…
    a = search_repo(workspace, n=1)
    b = search_repo(other, n=1)
    assert a["files"] == b["files"]
    assert a["total_matches"] == b["total_matches"]
    assert a["digest"] == b["digest"]
    # …but seed metadata (and thus the overall agent checksum) still differs.
    assert (workspace / "SEED.txt").read_text(encoding="utf-8") == "42\n1\n"
    assert (other / "SEED.txt").read_text(encoding="utf-8") == "7\n1\n"
