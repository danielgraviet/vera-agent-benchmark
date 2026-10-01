"""Scaling helpers that drive module/case/burn volume (and thus checksums)."""

from __future__ import annotations

import pytest

from workload.coding_loop import _burn_iters, _n_cases, _n_modules


@pytest.mark.parametrize(
    ("n", "modules", "cases", "burn"),
    [
        (1, 8, 128, 12000),
        (2, 9, 128, 12000),
        (5, 10, 164, 12500),
        (10, 13, 264, 17000),
        (20, 18, 464, 26000),
        (45, 30, 964, 48500),
        # clamps
        (0, 8, 128, 12000),
        (10_000, 96, 8000, 200000),
    ],
)
def test_scaling_table(n: int, modules: int, cases: int, burn: int) -> None:
    assert _n_modules(n) == modules
    assert _n_cases(n) == cases
    assert _burn_iters(n) == burn


def test_scaling_monotone_nondecreasing() -> None:
    prev_m = prev_c = prev_b = -1
    for n in range(0, 200, 7):
        m, c, b = _n_modules(n), _n_cases(n), _burn_iters(n)
        assert m >= prev_m
        assert c >= prev_c
        assert b >= prev_b
        prev_m, prev_c, prev_b = m, c, b
