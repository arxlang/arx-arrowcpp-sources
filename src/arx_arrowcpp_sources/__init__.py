"""
title: Locate the bundled Apache Arrow C++ source artifacts.
"""

from arx_arrowcpp_sources._bundle import (
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
    package_root,
    read_bundle_metadata,
)
from arx_arrowcpp_sources._version import __version__

__all__ = [
    "__version__",
    "bundle_root",
    "bundled_arrowcpp_tag",
    "bundled_arrowcpp_version",
    "get_cmake_dir",
    "get_cmake_files",
    "get_cpp_dir",
    "get_cpp_source_files",
    "get_format_dir",
    "get_header_files",
    "get_include_dir",
    "get_license_files",
    "get_source_dir",
    "get_source_files",
    "get_source_root",
    "package_root",
    "read_bundle_metadata",
]
