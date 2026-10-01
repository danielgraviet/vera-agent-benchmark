"""Oracle patches must fix the suite; edit payload is part of the checksum."""

from __future__ import annotations

from pathlib import Path

from workload.coding_loop import (
    _pytest,
    apply_oracle_patches,
    seed_workspace,
    verify_suite,
)


def test_oracle_edit_payload_is_stable(workspace: Path, golden: dict) -> None:
    seed_workspace(workspace, n=1, seed=42)
    edit = apply_oracle_patches(workspace)
    assert edit == golden["n1_seed42_steps"]["edit"]


def test_oracle_fixes_core_modules(workspace: Path) -> None:
    seed_workspace(workspace, n=1, seed=42)
    apply_oracle_patches(workspace)
    mathy = (workspace / "app" / "mathy.py").read_text(encoding="utf-8")
    stats = (workspace / "app" / "stats.py").read_text(encoding="utf-8")
    texty = (workspace / "app" / "texty.py").read_text(encoding="utf-8")
    assert "return a + b" in mathy
    assert "return a - b" not in mathy
    assert "return sum(xs) / len(xs)" in stats
    assert "strip().lower()" in texty
    # burn helper must survive the patch (CPU gate for parametrized tests)
    assert "def burn(" in mathy
    assert "0x9E3779B9" in mathy


def test_suite_passes_only_after_oracle(workspace: Path) -> None:
    seed_workspace(workspace, n=1, seed=42)
    broken = _pytest(workspace)
    assert broken.returncode != 0

    apply_oracle_patches(workspace)
    verify = verify_suite(workspace, precheck_exit=1)
    assert verify["passed"] is True
    assert verify["exit_code"] == 0
    assert verify["failed_count"] == 0
    assert verify["passed_count"] == 136
    assert verify["precheck_exit"] == 1
