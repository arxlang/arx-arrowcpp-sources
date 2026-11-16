"""
title: Check native tooling wheels for every supported CI Python version.
"""

from __future__ import annotations

import re
import tomllib

from pathlib import Path

import pytest

from packaging.tags import Tag, cpython_tags
from packaging.utils import parse_wheel_filename

PROJECT_DIR = Path(__file__).resolve().parent.parent
PROJECT = tomllib.loads((PROJECT_DIR / "pyproject.toml").read_text())[
    "project"
]
PYTHON_VERSIONS = [
    tuple(int(part) for part in match.group(1).split("."))
    for classifier in PROJECT["classifiers"]
    if (
        match := re.fullmatch(
            r"Programming Language :: Python :: (3\.[0-9]+)", classifier
        )
    )
]


@pytest.mark.parametrize("python_version", PYTHON_VERSIONS)
def test_locked_rpds_has_compatible_linux_wheel(
    python_version: tuple[int, ...],
) -> None:
    """
    title: Avoid unsupported PyO3 source builds in the Ubuntu CI matrix.
    parameters:
      python_version:
        type: tuple[int, Ellipsis]
    """
    lock = tomllib.loads((PROJECT_DIR / "poetry.lock").read_text())
    rpds = next(
        package for package in lock["package"] if package["name"] == "rpds-py"
    )
    wheel_tags: set[Tag] = set()
    for file in rpds["files"]:
        if not file["file"].endswith(".whl"):
            continue
        _, _, _, tags = parse_wheel_filename(file["file"])
        wheel_tags.update(
            tag
            for tag in tags
            if tag.platform.startswith("manylinux")
            and tag.platform.endswith("_x86_64")
        )
    platforms = sorted({tag.platform for tag in wheel_tags})
    abi = "cp" + "".join(str(part) for part in python_version)
    supported_tags = set(
        cpython_tags(
            python_version=python_version, abis=[abi], platforms=platforms
        )
    )
    assert wheel_tags & supported_tags, (
        f"Locked rpds-py {rpds['version']} has no compatible Linux x86_64 "
        f"wheel for Python {'.'.join(str(part) for part in python_version)}"
    )
