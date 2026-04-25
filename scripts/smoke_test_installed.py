"""
title: Smoke test an installed arx-arrowcpp-sources wheel.
"""

from __future__ import annotations

from pathlib import Path

from arx_arrowcpp_sources import (
    bundle_root,
    bundled_arrowcpp_tag,
    bundled_arrowcpp_version,
    get_cmake_dir,
    get_cpp_dir,
    get_format_dir,
    get_include_dir,
    get_license_files,
    read_bundle_metadata,
)


def main() -> None:
    """
    title: Validate key files from an installed package artifact.
    """
    root = bundle_root()
    metadata = read_bundle_metadata()

    _assert_file(root / "bundle-metadata.json")
    _assert_file(root / "LICENSE.txt")
    _assert_file(root / "NOTICE.txt")
    _assert_file(get_cpp_dir() / "CMakeLists.txt")
    _assert_file(get_include_dir() / "arrow" / "api.h")
    _assert_dir(get_format_dir())
    _assert_dir(get_cmake_dir())

    license_files = {path.name for path in get_license_files()}
    if not {"LICENSE.txt", "NOTICE.txt"}.issubset(license_files):
        raise AssertionError(
            "Installed package is missing Apache Arrow license/notice files"
        )

    if metadata["bundled_version"] != bundled_arrowcpp_version():
        raise AssertionError("Installed metadata bundled_version mismatch")
    if metadata["bundled_tag"] != bundled_arrowcpp_tag():
        raise AssertionError("Installed metadata bundled_tag mismatch")
    if "cpp/src/arrow/api.h" not in metadata["header_files"]:
        raise AssertionError("Installed metadata is missing arrow/api.h")
    if "cpp/CMakeLists.txt" not in metadata["cmake_files"]:
        raise AssertionError(
            "Installed metadata is missing cpp/CMakeLists.txt"
        )


def _assert_file(path: Path) -> None:
    """
    title: Assert that a path exists as a file.
    parameters:
      path:
        type: Path
    """
    if not path.is_file():
        raise AssertionError(f"Expected installed file to exist: {path}")


def _assert_dir(path: Path) -> None:
    """
    title: Assert that a path exists as a directory.
    parameters:
      path:
        type: Path
    """
    if not path.is_dir():
        raise AssertionError(f"Expected installed directory to exist: {path}")


if __name__ == "__main__":
    main()
