"""
title: Build the vendored Apache Arrow C++ source tree.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request

from collections.abc import Iterable
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from arx_arrowcpp_sources._version import (  # noqa: E402
    BUNDLED_ARROWCPP_SHA256,
    BUNDLED_ARROWCPP_TAG,
    BUNDLED_ARROWCPP_VERSION,
)

PACKAGE_DIR = SRC_DIR / "arx_arrowcpp_sources"
VENDOR_DIR = PACKAGE_DIR / "vendor"
UPSTREAM_ARCHIVE_NAME = f"apache-arrow-{BUNDLED_ARROWCPP_VERSION}.tar.gz"
UPSTREAM_ARCHIVE_URLS = (
    "https://downloads.apache.org/arrow/"
    f"arrow-{BUNDLED_ARROWCPP_VERSION}/{UPSTREAM_ARCHIVE_NAME}",
    "https://archive.apache.org/dist/arrow/"
    f"arrow-{BUNDLED_ARROWCPP_VERSION}/{UPSTREAM_ARCHIVE_NAME}",
)
VENDORED_DIRECTORIES = ("cpp", "format")
VENDORED_ROOT_FILES = (
    "CHANGELOG.md",
    "LICENSE.txt",
    "NOTICE.txt",
    "README.md",
)
SOURCE_SUFFIXES = (".c", ".cc", ".cpp", ".cxx")
HEADER_SUFFIXES = (".h", ".hh", ".hpp", ".hxx", ".inc")


def build_bundle() -> None:
    """
    title: Download and vendor the Apache Arrow C++ source release subset.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / UPSTREAM_ARCHIVE_NAME
        extracted_root = tmp_path / "upstream"

        downloaded_url = _download_archive(archive_path)
        _verify_archive(archive_path)
        _extract_archive(archive_path, extracted_root)

        upstream_root = _find_upstream_root(extracted_root)
        _sync_vendor_tree(upstream_root, downloaded_url)


def _download_archive(target_path: Path) -> str:
    """
    title: Download the Apache Arrow source archive to a local path.
    parameters:
      target_path:
        type: Path
    returns:
      type: str
    """
    last_error: Exception | None = None

    for url in UPSTREAM_ARCHIVE_URLS:
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                with target_path.open("wb") as output_file:
                    shutil.copyfileobj(response, output_file)
            return url
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc

    raise RuntimeError(
        "Unable to download Apache Arrow source archive from any known URL"
    ) from last_error


def _verify_archive(archive_path: Path) -> None:
    """
    title: Verify the downloaded source archive checksum.
    parameters:
      archive_path:
        type: Path
    """
    digest = hashlib.sha256()
    with archive_path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)

    actual = digest.hexdigest()
    if actual != BUNDLED_ARROWCPP_SHA256:
        raise ValueError(
            "Downloaded Apache Arrow source archive failed SHA256 "
            f"verification: expected {BUNDLED_ARROWCPP_SHA256}, got {actual}"
        )


def _extract_archive(archive_path: Path, output_dir: Path) -> None:
    """
    title: Safely extract regular files and directories from the archive.
    parameters:
      archive_path:
        type: Path
      output_dir:
        type: Path
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            if not _should_extract_archive_member(member):
                continue
            target_path = output_dir / member.name
            if member.isdir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            source_file = archive.extractfile(member)
            if source_file is None:
                raise ValueError(
                    "Supported archive member cannot be read as a file: "
                    f"{member.name}"
                )
            try:
                with target_path.open("wb") as output_file:
                    shutil.copyfileobj(source_file, output_file)
            finally:
                source_file.close()


def _should_extract_archive_member(member: tarfile.TarInfo) -> bool:
    """
    title: Return whether one archive member should be extracted.
    parameters:
      member:
        type: tarfile.TarInfo
    returns:
      type: bool
    """
    member_path = Path(member.name)
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"Archive contains an unsafe path: {member.name}")
    return member.isdir() or member.isfile()


def _find_upstream_root(output_dir: Path) -> Path:
    """
    title: Locate the extracted Apache Arrow source root.
    parameters:
      output_dir:
        type: Path
    returns:
      type: Path
    """
    for child in output_dir.iterdir():
        cpp_cmake = child / "cpp" / "CMakeLists.txt"
        arrow_api_header = child / "cpp" / "src" / "arrow" / "api.h"
        format_dir = child / "format"
        if (
            child.is_dir()
            and cpp_cmake.exists()
            and arrow_api_header.exists()
            and format_dir.exists()
        ):
            return child

    raise FileNotFoundError(
        "Unable to locate extracted Apache Arrow source tree"
    )


def _sync_vendor_tree(upstream_root: Path, downloaded_url: str) -> None:
    """
    title: Replace the package vendor tree with the selected upstream files.
    parameters:
      upstream_root:
        type: Path
      downloaded_url:
        type: str
    """
    if VENDOR_DIR.exists():
        shutil.rmtree(VENDOR_DIR)
    VENDOR_DIR.mkdir(parents=True)

    for directory_name in VENDORED_DIRECTORIES:
        shutil.copytree(
            upstream_root / directory_name,
            VENDOR_DIR / directory_name,
        )

    for file_name in VENDORED_ROOT_FILES:
        shutil.copy2(upstream_root / file_name, VENDOR_DIR / file_name)

    metadata = _build_metadata(downloaded_url)
    (VENDOR_DIR / "bundle-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf8",
    )


def _build_metadata(downloaded_url: str) -> dict[str, object]:
    """
    title: Build metadata describing the vendored source tree.
    parameters:
      downloaded_url:
        type: str
    returns:
      type: dict[str, object]
    """
    return {
        "bundled_version": BUNDLED_ARROWCPP_VERSION,
        "bundled_tag": BUNDLED_ARROWCPP_TAG,
        "source_archive_url": downloaded_url,
        "source_archive_urls": list(UPSTREAM_ARCHIVE_URLS),
        "source_archive_sha256": BUNDLED_ARROWCPP_SHA256,
        "vendored_directories": list(VENDORED_DIRECTORIES),
        "vendored_root_files": list(VENDORED_ROOT_FILES),
        "cpp_dir": "cpp",
        "format_dir": "format",
        "include_dir": "cpp/src",
        "cmake_dir": "cpp",
        "header_files": _relative_files(
            VENDOR_DIR / "cpp" / "src",
            HEADER_SUFFIXES,
        ),
        "source_files": _relative_files(
            VENDOR_DIR / "cpp" / "src",
            SOURCE_SUFFIXES,
        ),
        "cmake_files": _relative_cmake_files(VENDOR_DIR / "cpp"),
    }


def _relative_files(root: Path, suffixes: Iterable[str]) -> list[str]:
    """
    title: List vendored files below a root with selected suffixes.
    parameters:
      root:
        type: Path
      suffixes:
        type: Iterable[str]
    returns:
      type: list[str]
    """
    suffix_set = set(suffixes)
    return [
        path.relative_to(VENDOR_DIR).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in suffix_set
    ]


def _relative_cmake_files(root: Path) -> list[str]:
    """
    title: List vendored CMake files below a root.
    parameters:
      root:
        type: Path
    returns:
      type: list[str]
    """
    files = [path for path in root.rglob("*.cmake") if path.is_file()]
    files.extend(
        path for path in root.rglob("CMakeLists.txt") if path.is_file()
    )
    return [path.relative_to(VENDOR_DIR).as_posix() for path in sorted(files)]


if __name__ == "__main__":
    build_bundle()
