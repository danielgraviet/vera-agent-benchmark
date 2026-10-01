"""Full coding loop + golden checksums (primary regression net)."""

from __future__ import annotations

from pathlib import Path

import pytest

from workload.agent import compute_checksum
from workload.coding_loop import run_coding_loop


def _checksum_for(workspace: Path, *, n: int, seed: int) -> tuple[str, dict]:
    steps = run_coding_loop(workspace, n=n, seed=seed)
    checksum = compute_checksum(
        steps["seed"],
        steps["search"],
        steps["ast"],
        steps["edit"],
        steps["verify"],
    )
    return checksum, steps


@pytest.mark.parametrize(
    ("key", "n", "seed"),
    [
        ("n1_seed42", 1, 42),
        ("n1_seed7", 1, 7),
        ("n2_seed42", 2, 42),
        ("n5_seed42", 5, 42),
    ],
)
def test_golden_checksums(
    workspace: Path, golden: dict, key: str, n: int, seed: int
) -> None:
    checksum, steps = _checksum_for(workspace, n=n, seed=seed)
    assert checksum == golden["checksums"][key]
    assert steps["verify"]["passed"] is True
    assert steps["verify"]["exit_code"] == 0
    assert steps["verify"]["failed_count"] == 0
    assert steps["verify"]["precheck_exit"] != 0


def test_n1_seed42_step_payloads_match_golden(workspace: Path, golden: dict) -> None:
    checksum, steps = _checksum_for(workspace, n=1, seed=42)
    expected = golden["n1_seed42_steps"]
    assert checksum == golden["checksums"]["n1_seed42"]
    assert steps["seed"] == expected["seed_meta"]
    assert steps["search"] == expected["search"]
    assert steps["ast"] == expected["ast"]
    assert steps["edit"] == expected["edit"]
    assert steps["verify"] == expected["verify"]


def test_checksum_deterministic_across_runs(tmp_path: Path) -> None:
    results = []
    for i in range(2):
        ws = tmp_path / f"run_{i}"
        ws.mkdir()
        checksum, _ = _checksum_for(ws, n=1, seed=42)
        results.append(checksum)
    assert results[0] == results[1]


def test_checksum_changes_when_seed_changes(tmp_path: Path, golden: dict) -> None:
    a_ws = tmp_path / "a"
    b_ws = tmp_path / "b"
    a_ws.mkdir()
    b_ws.mkdir()
    a, _ = _checksum_for(a_ws, n=1, seed=42)
    b, _ = _checksum_for(b_ws, n=1, seed=7)
    assert a == golden["checksums"]["n1_seed42"]
    assert b == golden["checksums"]["n1_seed7"]
    assert a != b


def test_checksum_changes_when_n_changes(tmp_path: Path, golden: dict) -> None:
    a_ws = tmp_path / "a"
    b_ws = tmp_path / "b"
    a_ws.mkdir()
    b_ws.mkdir()
    a, _ = _checksum_for(a_ws, n=1, seed=42)
    b, steps_b = _checksum_for(b_ws, n=2, seed=42)
    assert a == golden["checksums"]["n1_seed42"]
    assert b == golden["checksums"]["n2_seed42"]
    assert a != b
    # n=2 adds a module → search/ast file counts differ
    assert steps_b["seed"]["n_modules"] == 9
    assert steps_b["search"]["files"] == 13


def test_compute_checksum_is_order_sensitive() -> None:
    a = compute_checksum({"x": 1}, {"y": 2})
    b = compute_checksum({"y": 2}, {"x": 1})
    assert a != b


def test_compute_checksum_sorts_dict_keys() -> None:
    assert compute_checksum({"b": 1, "a": 2}) == compute_checksum({"a": 2, "b": 1})


def test_run_coding_loop_rejects_already_passing_seed(
    workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If precheck unexpectedly passes, the loop must fail loudly."""
    from workload import coding_loop

    class FakeProc:
        returncode = 0
        stdout = "2 passed"
        stderr = ""

    seed_calls = {"n": 0}

    def fake_seed(workspace: Path, *, n: int, seed: int) -> dict:
        seed_calls["n"] += 1
        (workspace / "app").mkdir(parents=True, exist_ok=True)
        (workspace / "app" / "x.py").write_text("x=1\n", encoding="utf-8")
        (workspace / "tests").mkdir(parents=True, exist_ok=True)
        return {"n_modules": 0, "n_cases": 0, "burn_rounds": 0, "seed": seed}

    monkeypatch.setattr(coding_loop, "seed_workspace", fake_seed)
    monkeypatch.setattr(coding_loop, "_pytest", lambda *a, **k: FakeProc())
    with pytest.raises(RuntimeError, match="expected failing suite"):
        run_coding_loop(workspace, n=1, seed=42)
