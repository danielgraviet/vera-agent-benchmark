"""Workspace seed: layout, bugs present, determinism."""

from __future__ import annotations

from pathlib import Path

from workload.coding_loop import _pytest, seed_workspace


def test_seed_workspace_layout_and_meta(workspace: Path, golden: dict) -> None:
    meta = seed_workspace(workspace, n=1, seed=42)
    expected = golden["n1_seed42_steps"]["seed_meta"]
    assert meta == expected

    app = workspace / "app"
    assert (app / "__init__.py").is_file()
    assert (app / "mathy.py").is_file()
    assert (app / "stats.py").is_file()
    assert (app / "texty.py").is_file()

    util_files = sorted(app.glob("util_*.py"))
    assert len(util_files) == expected["n_modules"]
    assert util_files[0].name == "util_000.py"
    assert util_files[-1].name == f"util_{expected['n_modules'] - 1:03d}.py"

    tests = workspace / "tests"
    assert (tests / "test_mathy.py").is_file()
    assert (tests / "test_stats.py").is_file()
    assert (tests / "test_texty.py").is_file()
    assert (tests / "hidden" / "test_extra.py").is_file()
    assert (workspace / "SEED.txt").read_text(encoding="utf-8") == "42\n1\n"


def test_seed_contains_intentional_bugs(workspace: Path) -> None:
    seed_workspace(workspace, n=1, seed=42)
    mathy = (workspace / "app" / "mathy.py").read_text(encoding="utf-8")
    stats = (workspace / "app" / "stats.py").read_text(encoding="utf-8")
    texty = (workspace / "app" / "texty.py").read_text(encoding="utf-8")
    assert "return a - b" in mathy
    assert "return sum(xs)  # bug" in stats
    assert "return s  # bug" in texty


def test_seed_generated_modules_embed_seed(workspace: Path) -> None:
    seed_workspace(workspace, n=2, seed=99)
    util0 = (workspace / "app" / "util_000.py").read_text(encoding="utf-8")
    assert "seed=99" in util0
    assert "VALUE_0 = 99" in util0


def test_seed_is_deterministic(workspace: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    seed_workspace(workspace, n=3, seed=11)
    seed_workspace(other, n=3, seed=11)

    def fingerprint(root: Path) -> dict[str, str]:
        return {
            str(p.relative_to(root)): p.read_text(encoding="utf-8")
            for p in sorted(root.rglob("*"))
            if p.is_file()
        }

    assert fingerprint(workspace) == fingerprint(other)


def test_precheck_fails_on_broken_suite(workspace: Path) -> None:
    seed_workspace(workspace, n=1, seed=42)
    pre = _pytest(workspace, "test_stats.py", "test_texty.py")
    assert pre.returncode != 0
