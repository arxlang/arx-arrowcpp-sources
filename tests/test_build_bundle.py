"""
title: Offline tests for verified Apache Arrow bundle generation.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import urllib.error
import zipfile

from pathlib import Path
from unittest.mock import Mock

import pytest

from arx_arrowcpp_sources._version import BUNDLED_ARROWCPP_VERSION
from poetry.core.factory import Factory
from poetry.core.masonry.builders.sdist import SdistBuilder
from poetry.core.masonry.builders.wheel import WheelBuilder

from scripts import build_bundle


def source_archive(version: str) -> bytes:
    """
    title: Create a minimal source release with the upstream layout.
    parameters:
      version:
        type: str
    returns:
      type: bytes
    """
    files = {
        "cpp/CMakeLists.txt": f'set(ARROW_VERSION "{version}")\n',
        "cpp/src/arrow/api.h": "// Arrow API\n",
        "cpp/src/arrow/builder.cc": "// Arrow implementation\n",
        "format/Schema.fbs": "// Arrow schema\n",
        **dict.fromkeys(
            build_bundle.VENDORED_ROOT_FILES, "Release metadata\n"
        ),
    }
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, content in files.items():
            data = content.encode()
            member = tarfile.TarInfo(f"apache-arrow-{version}/{name}")
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def test_build_verified_bundle_with_archive_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Build a verified bundle and record the fallback download URL.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    archive = source_archive(BUNDLED_ARROWCPP_VERSION)
    checksum = hashlib.sha256(archive).hexdigest()
    vendor = tmp_path / "vendor"
    monkeypatch.setattr(build_bundle, "VENDOR_DIR", vendor)
    monkeypatch.setattr(build_bundle, "BUNDLED_ARROWCPP_SHA256", checksum)
    download = Mock(
        side_effect=[urllib.error.URLError("retired"), io.BytesIO(archive)]
    )
    monkeypatch.setattr(
        "scripts.build_bundle.urllib.request.urlopen", download
    )
    build_bundle.build_bundle()
    metadata = json.loads((vendor / "bundle-metadata.json").read_text())
    assert metadata["bundled_version"] == BUNDLED_ARROWCPP_VERSION
    assert metadata["source_archive_sha256"] == checksum
    assert (
        metadata["source_archive_url"] == build_bundle.UPSTREAM_ARCHIVE_URLS[1]
    )
    assert "cpp/src/arrow/api.h" in metadata["header_files"]
    assert "cpp/src/arrow/builder.cc" in metadata["source_files"]
    assert "cpp/CMakeLists.txt" in metadata["cmake_files"]
    assert ".env" in metadata["vendored_root_files"]
    for name in build_bundle.VENDORED_ROOT_FILES:
        assert (vendor / name).is_file()


@pytest.mark.parametrize("failure", ["checksum", "version"])
def test_invalid_archive_does_not_replace_existing_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """
    title: Validate checksum and source version before replacing a bundle.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
      failure:
        type: str
    """
    archive = source_archive("1.0.0")
    checksum = hashlib.sha256(archive).hexdigest()
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    sentinel = vendor / "existing"
    sentinel.write_text("Previous bundle\n")
    monkeypatch.setattr(build_bundle, "VENDOR_DIR", vendor)
    monkeypatch.setattr(
        build_bundle,
        "BUNDLED_ARROWCPP_SHA256",
        checksum if failure == "version" else "0" * 64,
    )
    monkeypatch.setattr(
        "scripts.build_bundle.urllib.request.urlopen",
        Mock(return_value=io.BytesIO(archive)),
    )
    expected = "version" if failure == "version" else "SHA256"
    with pytest.raises(ValueError, match=expected):
        build_bundle.build_bundle()
    assert list(vendor.iterdir()) == [sentinel]
    assert sentinel.read_text() == "Previous bundle\n"


def test_wheel_and_sdist_preserve_cmake_dotfile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Package a synthetic bundle and retain CMake's required dotfile.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    root = Path(__file__).resolve().parent.parent
    project = tmp_path / "project"
    project.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE", ".gitignore"):
        shutil.copy2(root / name, project / name)
    package_path = Path("src/arx_arrowcpp_sources")
    shutil.copytree(
        root / package_path,
        project / package_path,
        ignore=shutil.ignore_patterns("vendor", "__pycache__"),
    )
    archive_path = tmp_path / "release.tar.gz"
    archive_path.write_bytes(source_archive(BUNDLED_ARROWCPP_VERSION))
    extracted = tmp_path / "extracted"
    build_bundle._extract_archive(archive_path, extracted)
    upstream_root = build_bundle._find_upstream_root(extracted)
    monkeypatch.setattr(
        build_bundle, "VENDOR_DIR", project / package_path / "vendor"
    )
    build_bundle._sync_vendor_tree(
        upstream_root, "https://example.invalid/test.tar.gz"
    )
    poetry = Factory().create_poetry(project)
    wheel = WheelBuilder(poetry).build(tmp_path / "dist")
    sdist = SdistBuilder(poetry).build(tmp_path / "dist")
    with zipfile.ZipFile(wheel) as artifact:
        assert "arx_arrowcpp_sources/vendor/.env" in artifact.namelist()
        assert (
            "arx_arrowcpp_sources/vendor/cpp/src/arrow/api.h"
            in artifact.namelist()
        )
    with tarfile.open(sdist) as artifact:
        assert any(
            name.endswith("src/arx_arrowcpp_sources/vendor/.env")
            for name in artifact.getnames()
        )
