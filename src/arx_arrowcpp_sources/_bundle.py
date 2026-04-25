"""
title: Helper functions for locating the packaged Apache Arrow C++ sources.
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import TypedDict, cast

from arx_arrowcpp_sources._version import (
    BUNDLED_ARROWCPP_TAG,
    BUNDLED_ARROWCPP_VERSION,
)

_SOURCE_SUFFIXES = (".c", ".cc", ".cpp", ".cxx")
_HEADER_SUFFIXES = (".h", ".hh", ".hpp", ".hxx", ".inc")


class BundleMetadata(TypedDict):
    bundled_tag: str
    bundled_version: str
    cmake_dir: str
    cmake_files: list[str]
    cpp_dir: str
    format_dir: str
    header_files: list[str]
    include_dir: str
    source_archive_sha256: str
    source_archive_url: str
    source_archive_urls: list[str]
    source_files: list[str]
    vendored_directories: list[str]
    vendored_root_files: list[str]


def package_root() -> Path:
    """
    title: Return the root directory of the installed package.
    returns:
      type: Path
    """
    return Path(__file__).resolve().parent


def bundle_root() -> Path:
    """
    title: Return the root directory of the vendored Apache Arrow source tree.
    returns:
      type: Path
    """
    root = package_root() / "vendor"
    metadata_path = root / "bundle-metadata.json"
    if not root.exists() or not metadata_path.exists():
        raise FileNotFoundError(
            "Bundled Apache Arrow C++ sources are missing. "
            "Run 'python scripts/build_bundle.py' before building/testing."
        )
    return root


def get_source_root() -> Path:
    """
    title: Return the root directory of the vendored Apache Arrow source tree.
    returns:
      type: Path
    """
    return bundle_root()


def get_cpp_dir() -> Path:
    """
    title: Return the vendored Apache Arrow C++ project directory.
    returns:
      type: Path
    """
    return bundle_root() / "cpp"


def get_format_dir() -> Path:
    """
    title: Return the vendored Apache Arrow FlatBuffers format directory.
    returns:
      type: Path
    """
    return bundle_root() / "format"


def get_include_dir() -> Path:
    """
    title: Return the include directory containing Apache Arrow C++ headers.
    returns:
      type: Path
    """
    return get_cpp_dir() / "src"


def get_source_dir() -> Path:
    """
    title: Return the directory containing Apache Arrow C++ library sources.
    returns:
      type: Path
    """
    return get_cpp_dir() / "src"


def get_cmake_dir() -> Path:
    """
    title: Return the directory containing Apache Arrow C++ CMake entrypoints.
    returns:
      type: Path
    """
    return get_cpp_dir()


def get_header_files() -> tuple[Path, ...]:
    """
    title: Return the packaged Apache Arrow C++ header files.
    returns:
      type: tuple[Path, Ellipsis]
    """
    return _files_with_suffixes(get_include_dir(), _HEADER_SUFFIXES)


def get_cpp_source_files() -> tuple[Path, ...]:
    """
    title: Return packaged Apache Arrow C++ source files.
    returns:
      type: tuple[Path, Ellipsis]
    """
    return _files_with_suffixes(get_source_dir(), _SOURCE_SUFFIXES)


def get_source_files() -> tuple[Path, ...]:
    """
    title: Return packaged Apache Arrow compilable source files.
    returns:
      type: tuple[Path, Ellipsis]
    """
    return get_cpp_source_files()


def get_cmake_files() -> tuple[Path, ...]:
    """
    title: Return packaged Apache Arrow C++ CMake files.
    returns:
      type: tuple[Path, Ellipsis]
    """
    cmake_dir = get_cmake_dir()
    files = [path for path in cmake_dir.rglob("*.cmake") if path.is_file()]
    files.extend(
        path for path in cmake_dir.rglob("CMakeLists.txt") if path.is_file()
    )
    return tuple(sorted(files))


def get_license_files() -> tuple[Path, ...]:
    """
    title: Return the packaged Apache Arrow license and notice files.
    returns:
      type: tuple[Path, Ellipsis]
    """
    root = bundle_root()
    return tuple(
        path
        for path in sorted(root.glob("*"))
        if path.name.startswith(("LICENSE", "NOTICE"))
    )


def bundled_arrowcpp_version() -> str:
    """
    title: Return the Apache Arrow C++ version bundled by this package.
    returns:
      type: str
    """
    return BUNDLED_ARROWCPP_VERSION


def bundled_arrowcpp_tag() -> str:
    """
    title: Return the Apache Arrow git tag bundled by this package.
    returns:
      type: str
    """
    return BUNDLED_ARROWCPP_TAG


def read_bundle_metadata() -> BundleMetadata:
    """
    title: Return the stored metadata describing the vendored source tree.
    returns:
      type: BundleMetadata
    """
    metadata_path = bundle_root() / "bundle-metadata.json"
    return cast(
        BundleMetadata,
        json.loads(metadata_path.read_text(encoding="utf8")),
    )


def _files_with_suffixes(
    root: Path,
    suffixes: tuple[str, ...],
) -> tuple[Path, ...]:
    suffix_set = set(suffixes)
    return tuple(
        sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix in suffix_set
        )
    )
