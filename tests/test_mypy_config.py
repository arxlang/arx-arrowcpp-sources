"""
title: Keep optional NumPy stubs from changing project type-checking support.
"""

from __future__ import annotations

import subprocess
import sys

from pathlib import Path

import pytest

PROJECT_DIR = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize(
    ("source", "returncode", "output"),
    [
        ("import numpy\n", 0, "Success:"),
        ("import numpy.linalg\n", 0, "Success:"),
        (
            "import numpy\ndef untyped(value):\n    return value\n",
            1,
            "[no-untyped-def]",
        ),
    ],
    ids=["numpy-stub", "numpy-submodule-stub", "project-remains-strict"],
)
def test_mypy_skips_modern_numpy_stubs_but_keeps_project_strict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    returncode: int,
    output: str,
) -> None:
    """
    title: Reject project errors without parsing optional Python 3.12 stubs.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
      source:
        type: str
      returncode:
        type: int
      output:
        type: str
    """
    stubs = tmp_path / "stubs"
    numpy = stubs / "numpy"
    numpy.mkdir(parents=True)
    # PEP 695 syntax reproduces newer NumPy stubs that cannot be parsed for
    # our Python 3.11 target, regardless of the interpreter running mypy.
    (numpy / "__init__.pyi").write_text("type ModernAlias = int\n")
    (numpy / "linalg.pyi").write_text("type ModernNestedAlias = int\n")
    monkeypatch.setenv("MYPYPATH", str(stubs))
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(PROJECT_DIR / "pyproject.toml"),
            "--no-incremental",
            "--no-site-packages",
            "--cache-dir",
            str(tmp_path / "cache"),
            "-c",
            source,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    diagnostics = result.stdout + result.stderr
    assert result.returncode == returncode, diagnostics
    assert output in diagnostics
