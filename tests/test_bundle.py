"""
title: Tests for the packaged Apache Arrow C++ source helpers.
"""

from pathlib import Path

import arx_arrowcpp_sources._bundle as bundle_module
import pytest

from arx_arrowcpp_sources import (
    bundle_root,
    bundled_arrowcpp_tag,
    bundled_arrowcpp_version,
    get_cmake_dir,
    get_cmake_files,
    get_cpp_dir,
    get_cpp_source_files,
    get_format_dir,
    get_header_files,
    get_include_dir,
    get_license_files,
    get_source_dir,
    get_source_files,
    get_source_root,
    read_bundle_metadata,
)


def test_bundle_paths_exist() -> None:
    """
    title: Assert that the vendored Apache Arrow source paths exist.
    """
    assert bundle_root().exists()
    assert get_source_root().exists()
    assert get_cpp_dir().exists()
    assert get_format_dir().exists()
    assert get_include_dir().exists()
    assert get_source_dir().exists()
    assert get_cmake_dir().exists()
    assert get_header_files()
    assert get_cpp_source_files()
    assert get_source_files() == get_cpp_source_files()
    assert get_cmake_files()
    assert get_license_files()


def test_bundle_metadata_matches_helper_api() -> None:
    """
    title: Assert that bundle metadata matches the helper API.
    """
    metadata = read_bundle_metadata()

    assert metadata["bundled_version"] == bundled_arrowcpp_version()
    assert metadata["bundled_tag"] == bundled_arrowcpp_tag()
    assert metadata["cpp_dir"] == "cpp"
    assert metadata["format_dir"] == "format"
    assert metadata["include_dir"] == "cpp/src"
    assert "cpp/src/arrow/api.h" in metadata["header_files"]
    assert "cpp/src/arrow/builder.cc" in metadata["source_files"]
    assert "cpp/CMakeLists.txt" in metadata["cmake_files"]
    assert "LICENSE.txt" in metadata["vendored_root_files"]
    assert "NOTICE.txt" in metadata["vendored_root_files"]


def test_bundle_root_reports_missing_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    title: Assert that missing generated bundle contents fail clearly.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
      tmp_path:
        type: Path
    """

    def fake_package_root() -> Path:
        """
        title: Return a temporary empty package root for this test.
        returns:
          type: Path
        """
        return tmp_path

    monkeypatch.setattr(bundle_module, "package_root", fake_package_root)

    with pytest.raises(
        FileNotFoundError,
        match=r"Bundled Apache Arrow C\+\+ sources are missing",
    ):
        bundle_module.bundle_root()
