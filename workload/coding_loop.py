"""Coding-agent v3 loop: seed broken package → search → AST → patch → pytest.

Daytona-realistic offline work (no LLM, no network). Scales with ``n`` so chip
ladders spend seconds of in-sandbox CPU rather than create/toolbox tax.
"""

from __future__ import annotations

import ast
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

DEF_PATTERN = re.compile(r"\bdef \w+\(")
CLASS_PATTERN = re.compile(r"\bclass \w+")
IMPORT_PATTERN = re.compile(r"^(?:from|import)\s+", re.M)


def _n_modules(n: int) -> int:
    """Extra generated modules beyond the three core app files."""
    return max(8, min(96, 8 + n // 2))


def _n_cases(n: int) -> int:
    """Parametrized pytest cases — dominant CPU cost with per-case burn."""
    return max(128, min(8000, 64 + n * 20))


def _burn_iters(n: int) -> int:
    """Inner loop iterations inside each parametrized test."""
    return max(12000, min(200000, 8000 + n * 900))


def seed_workspace(workspace: Path, *, n: int, seed: int) -> dict[str, Any]:
    """Materialize a multi-file broken package + tests (deterministic)."""
    pkg = workspace / "app"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text('"""Broken customer package."""\n', encoding="utf-8")

    (pkg / "mathy.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a - b  # bug: should add\n"
        "\n"
        "def clamp(x: int, lo: int, hi: int) -> int:\n"
        "    return x  # bug: ignore bounds\n"
        "\n"
        "def burn(k: int, rounds: int) -> int:\n"
        "    '''Deterministic CPU filler used by parametrized tests.'''\n"
        "    x = (k ^ 0x9E3779B9) & 0xFFFFFFFF\n"
        "    for i in range(rounds):\n"
        "        x = (x * 1664525 + 1013904223 + i) & 0xFFFFFFFF\n"
        "        x ^= (x >> 16)\n"
        "    return x\n",
        encoding="utf-8",
    )
    (pkg / "stats.py").write_text(
        "def mean(xs: list[float]) -> float:\n"
        "    return sum(xs)  # bug: missing / len\n"
        "\n"
        "def moving_sum(xs: list[int], window: int) -> list[int]:\n"
        "    return xs  # bug: stub\n",
        encoding="utf-8",
    )
    (pkg / "texty.py").write_text(
        "def normalize(s: str) -> str:\n"
        "    return s  # bug: should strip + lower\n"
        "\n"
        "def token_count(s: str) -> int:\n"
        "    return len(s)  # bug: should split on whitespace\n",
        encoding="utf-8",
    )

    # Extra modules: searchable AST bulk (coding-agent repo walk).
    n_mod = _n_modules(n)
    for i in range(n_mod):
        body_lines = [
            f'"""Generated module {i} (seed={seed})."""',
            f"VALUE_{i} = {seed + i}",
            "",
            f"class Helper_{i}:",
            f"    TAG = {i}",
            f"    def transform(self, x: int) -> int:",
            f"        return x + VALUE_{i}",
            f"    def fold(self, xs: list[int]) -> int:",
            f"        total = 0",
            f"        for v in xs:",
            f"            total += self.transform(v)",
            f"        return total",
            "",
            f"def compute_{i}(x: int) -> int:",
            f"    return Helper_{i}().transform(x)",
            "",
            f"def scan_{i}(xs: list[int]) -> int:",
            f"    return Helper_{i}().fold(xs)",
            "",
            f"def digest_{i}(xs: list[int]) -> str:",
            f"    h = 0",
            f"    for v in xs:",
            f"        h = (h * 131 + compute_{i}(v)) & 0xFFFFFFFF",
            f"    return f'{{h:08x}}'",
        ]
        (pkg / f"util_{i:03d}.py").write_text("\n".join(body_lines) + "\n", encoding="utf-8")

    tests = workspace / "tests"
    tests.mkdir(parents=True)
    (tests / "conftest.py").write_text("", encoding="utf-8")

    n_cases = _n_cases(n)
    burn_rounds = _burn_iters(n)
    cases = "\n".join(f"    ({i}, {i + 1}, {2 * i + 1})," for i in range(n_cases))
    (tests / "test_mathy.py").write_text(
        "import pytest\n"
        "from app.mathy import add, clamp, burn\n"
        "\n"
        f"BURN_ROUNDS = {burn_rounds}\n"
        "\n"
        f"@pytest.mark.parametrize('a,b,expected', [\n{cases}\n])\n"
        "def test_add(a, b, expected):\n"
        "    # CPU-visible verify: burn then assert (coding-agent pytest gate)\n"
        "    _ = burn(a + b, BURN_ROUNDS)\n"
        "    assert add(a, b) == expected\n"
        "\n"
        "def test_clamp():\n"
        "    assert clamp(5, 0, 10) == 5\n"
        "    assert clamp(-1, 0, 10) == 0\n"
        "    assert clamp(99, 0, 10) == 10\n",
        encoding="utf-8",
    )
    (tests / "test_stats.py").write_text(
        "from app.stats import mean, moving_sum\n"
        "\n"
        "def test_mean():\n"
        "    assert mean([2.0, 4.0, 6.0]) == 4.0\n"
        "\n"
        "def test_moving_sum():\n"
        "    assert moving_sum([1, 2, 3, 4], 2) == [3, 5, 7]\n",
        encoding="utf-8",
    )
    (tests / "test_texty.py").write_text(
        "from app.texty import normalize, token_count\n"
        "\n"
        "def test_normalize():\n"
        "    assert normalize('  Hi THERE ') == 'hi there'\n"
        "\n"
        "def test_token_count():\n"
        "    assert token_count('a b  c') == 3\n",
        encoding="utf-8",
    )
    hidden = tests / "hidden"
    hidden.mkdir(parents=True)
    (hidden / "__init__.py").write_text("", encoding="utf-8")
    (hidden / "test_extra.py").write_text(
        "from app.mathy import clamp, burn\n"
        "from app.stats import mean\n"
        "\n"
        f"def test_burn_stable():\n"
        f"    assert burn(7, {max(8000, burn_rounds // 2)}) != 0\n"
        "\n"
        "def test_mean_empty():\n"
        "    assert mean([]) == 0.0\n"
        "\n"
        "def test_clamp_inverted_bounds():\n"
        "    assert clamp(5, 10, 0) == 5\n"
        "    assert clamp(-1, 10, 0) == 0\n"
        "    assert clamp(99, 10, 0) == 10\n",
        encoding="utf-8",
    )
    (workspace / "SEED.txt").write_text(f"{seed}\n{n}\n", encoding="utf-8")
    return {
        "n_modules": n_mod,
        "n_cases": n_cases,
        "burn_rounds": burn_rounds,
        "seed": seed,
    }


def search_repo(workspace: Path, *, n: int) -> dict[str, Any]:
    """Rip many files/patterns — full-tree pass per outer iteration."""
    files = sorted((workspace / "app").glob("*.py"))
    if not files:
        raise RuntimeError("no app/*.py to search")
    total_matches = 0
    digest = hashlib.sha256()
    for i in range(n):
        for path in files:
            text = path.read_text(encoding="utf-8")
            matches = (
                len(DEF_PATTERN.findall(text))
                + len(CLASS_PATTERN.findall(text))
                + len(IMPORT_PATTERN.findall(text))
            )
            total_matches += matches
            digest.update(f"{i}:{path.name}:{matches}".encode())
    return {
        "iterations": n,
        "total_matches": total_matches,
        "files": len(files),
        "digest": digest.hexdigest(),
    }


def ast_repo(workspace: Path, *, n: int) -> dict[str, Any]:
    """Parse + structural counts over the tree (n full passes)."""
    files = sorted((workspace / "app").glob("*.py"))
    if not files:
        raise RuntimeError("no app/*.py to parse")
    total_functions = 0
    total_classes = 0
    digest = hashlib.sha256()
    for i in range(n):
        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
            functions = 0
            classes = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions += 1
                elif isinstance(node, ast.ClassDef):
                    classes += 1
            total_functions += functions
            total_classes += classes
            digest.update(f"{i}:{path.name}:{functions}:{classes}".encode())
    return {
        "iterations": n,
        "total_functions": total_functions,
        "total_classes": total_classes,
        "files": len(files),
        "digest": digest.hexdigest(),
    }


def apply_oracle_patches(workspace: Path) -> dict[str, Any]:
    """Scripted coding-agent edits: fix the three broken modules (keep burn)."""
    steps: list[str] = []
    (workspace / "app" / "mathy.py").write_text(
        "def add(a: int, b: int) -> int:\n"
        "    return a + b\n"
        "\n"
        "def clamp(x: int, lo: int, hi: int) -> int:\n"
        "    if lo > hi:\n"
        "        lo, hi = hi, lo\n"
        "    return max(lo, min(hi, x))\n"
        "\n"
        "def burn(k: int, rounds: int) -> int:\n"
        "    '''Deterministic CPU filler used by parametrized tests.'''\n"
        "    x = (k ^ 0x9E3779B9) & 0xFFFFFFFF\n"
        "    for i in range(rounds):\n"
        "        x = (x * 1664525 + 1013904223 + i) & 0xFFFFFFFF\n"
        "        x ^= (x >> 16)\n"
        "    return x\n",
        encoding="utf-8",
    )
    steps.append("patched app/mathy.py")
    (workspace / "app" / "stats.py").write_text(
        "def mean(xs: list[float]) -> float:\n"
        "    if not xs:\n"
        "        return 0.0\n"
        "    return sum(xs) / len(xs)\n"
        "\n"
        "def moving_sum(xs: list[int], window: int) -> list[int]:\n"
        "    out = []\n"
        "    for i in range(len(xs) - window + 1):\n"
        "        out.append(sum(xs[i : i + window]))\n"
        "    return out\n",
        encoding="utf-8",
    )
    steps.append("patched app/stats.py")
    (workspace / "app" / "texty.py").write_text(
        "def normalize(s: str) -> str:\n"
        "    return ' '.join(s.strip().lower().split())\n"
        "\n"
        "def token_count(s: str) -> int:\n"
        "    return len(s.split())\n",
        encoding="utf-8",
    )
    steps.append("patched app/texty.py")
    return {"steps": steps, "patched_files": 3}


def _pytest(workspace: Path, *rel_paths: str) -> subprocess.CompletedProcess[str]:
    targets = [str(workspace / "tests" / p) for p in rel_paths] or [
        str(workspace / "tests")
    ]
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no", *targets],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONPATH": str(workspace), "PYTHONHASHSEED": "0"},
    )


def verify_suite(workspace: Path, *, precheck_exit: int) -> dict[str, Any]:
    """Full pytest including hidden tests (agent verify step).

    Checksum fields are counts/exit only. Do **not** include the raw pytest
    summary string — under pack it gains flaky ``N warnings`` / similar noise
    and blows ``distinct_checksums`` while exit_code stays 0 (seen on Phoenix
    c0p125 at 528/704).
    """
    proc = _pytest(workspace)
    passed = proc.returncode == 0
    out = proc.stdout or ""
    summary_line = ""
    for line in reversed(out.splitlines()):
        if "passed" in line or "failed" in line:
            summary_line = re.sub(r"\s+in\s+[\d.]+s\s*$", "", line.strip())
            break
    passed_n = failed_n = 0
    m = re.search(r"(\d+)\s+passed", summary_line)
    if m:
        passed_n = int(m.group(1))
    m = re.search(r"(\d+)\s+failed", summary_line)
    if m:
        failed_n = int(m.group(1))
    return {
        "passed": passed,
        "exit_code": proc.returncode,
        "passed_count": passed_n,
        "failed_count": failed_n,
        "precheck_exit": precheck_exit,
        # summary kept only for failure messages — not part of this dict's hash path
        # once omitted here (agent checksums the whole verify object).
    }


def run_coding_loop(workspace: Path, *, n: int, seed: int) -> dict[str, Any]:
    """Full v3 loop; returns step dicts for checksumming."""
    seed_result = seed_workspace(workspace, n=n, seed=seed)
    # Precheck only the small non-parametrized tests (cheap fail signal).
    pre = _pytest(workspace, "test_stats.py", "test_texty.py")
    if pre.returncode == 0:
        raise RuntimeError("expected failing suite before oracle patch")
    search_result = search_repo(workspace, n=n)
    ast_result = ast_repo(workspace, n=n)
    edit_result = apply_oracle_patches(workspace)
    verify_result = verify_suite(workspace, precheck_exit=pre.returncode)
    if not verify_result["passed"]:
        raise RuntimeError(
            f"verify failed: exit={verify_result['exit_code']} "
            f"passed={verify_result['passed_count']} "
            f"failed={verify_result['failed_count']}"
        )
    return {
        "seed": seed_result,
        "search": search_result,
        "ast": ast_result,
        "edit": edit_result,
        "verify": verify_result,
    }
