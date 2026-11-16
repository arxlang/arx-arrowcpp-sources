"""
title: Synchronize package releases with stable Apache Arrow releases.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import tomllib
import urllib.error
import urllib.request

from http import HTTPStatus
from pathlib import Path
from typing import Any, cast

PROJECT_DIR = Path(__file__).resolve().parent.parent
APACHE_DOWNLOADS = "https://downloads.apache.org/arrow/"
APACHE_ARCHIVE = "https://archive.apache.org/dist/arrow/"
PYPI = "https://pypi.org/pypi/"
STABLE_VERSION = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
VERSION_MODULE = "src/arx_arrowcpp_sources/_version.py"


def read_url(url: str) -> str:
    """
    title: Read upstream release metadata over HTTPS.
    parameters:
      url:
        type: str
    returns:
      type: str
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "arx-arrowcpp-sources/versioning"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return cast(bytes, response.read()).decode("utf8")


def version_tuple(version: str) -> tuple[int, ...]:
    """
    title: Validate and compare a stable upstream version.
    parameters:
      version:
        type: str
    returns:
      type: tuple[int, Ellipsis]
    """
    if re.fullmatch(STABLE_VERSION, version) is None:
        raise ValueError(f"Expected a stable Arrow X.Y.Z version: {version!r}")
    return tuple(int(part) for part in version.split("."))


def latest_arrow_version() -> str:
    """
    title: Discover the newest stable source release listed by Apache.
    returns:
      type: str
    """
    versions: list[str] = re.findall(
        rf'href="arrow-({STABLE_VERSION})/"', read_url(APACHE_DOWNLOADS)
    )
    if not versions:
        raise ValueError("Apache's download index contains no stable releases")
    return max(versions, key=version_tuple)


def pypi_release(package: str, version: str) -> dict[str, Any]:
    """
    title: Read metadata for one exact PyPI package release.
    parameters:
      package:
        type: str
      version:
        type: str
    returns:
      type: dict[str, Any]
    """
    return cast(
        dict[str, Any], json.loads(read_url(f"{PYPI}{package}/{version}/json"))
    )


def arrow_checksum(version: str) -> str:
    """
    title: Resolve Apache's SHA256 with an archived-release fallback.
    parameters:
      version:
        type: str
    returns:
      type: str
    """
    archive = f"apache-arrow-{version}.tar.gz"
    for base_url in (APACHE_DOWNLOADS, APACHE_ARCHIVE):
        try:
            source = read_url(f"{base_url}arrow-{version}/{archive}.sha256")
        except (urllib.error.URLError, TimeoutError):
            if base_url == APACHE_ARCHIVE:
                raise
            continue
        match = re.fullmatch(
            rf"([a-fA-F0-9]{{64}})(?:[ \t]+\*?{re.escape(archive)})?\s*",
            source.strip(),
        )
        if match is None:
            raise ValueError(f"Invalid Apache SHA256 file for Arrow {version}")
        return match.group(1).lower()
    raise RuntimeError("Unable to resolve Apache Arrow SHA256")


def read_versions() -> dict[str, str]:
    """
    title: Read literal version pins without importing stale modules.
    returns:
      type: dict[str, str]
    """
    tree = ast.parse((PROJECT_DIR / VERSION_MODULE).read_text(encoding="utf8"))
    return {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def replace_once(source: str, pattern: str, replacement: str) -> str:
    """
    title: Fail rather than silently leave a version reference stale.
    parameters:
      source:
        type: str
      pattern:
        type: str
      replacement:
        type: str
    returns:
      type: str
    """
    result, count = re.subn(pattern, lambda _: replacement, source, flags=re.M)
    if count != 1:
        raise ValueError(f"Expected exactly one version reference: {pattern}")
    return result


def sync_version(version: str, build: str = "") -> str:
    """
    title: Validate upstream metadata and synchronize local version pins.
    parameters:
      version:
        type: str
      build:
        type: str
    returns:
      type: str
    """
    version_tuple(version)
    if build and re.fullmatch(r"[0-9]+", build) is None:
        raise ValueError("Post-release build number must be numeric")
    current = read_versions()
    if version_tuple(version) < version_tuple(
        current["BUNDLED_ARROWCPP_VERSION"]
    ):
        raise ValueError(
            "Refusing to downgrade the bundled Apache Arrow release"
        )
    package_version = version
    if build:
        package_version = f"{version}.post{int(build)}"
        if (
            version == current["BUNDLED_ARROWCPP_VERSION"]
            and ".post" in current["PACKAGE_VERSION"]
            and int(build) < int(current["PACKAGE_VERSION"].split(".post")[1])
        ):
            raise ValueError("Refusing to downgrade the post-release build")
    elif version == current["BUNDLED_ARROWCPP_VERSION"]:
        # Scheduled runs must not reset an already-published .postN release.
        package_version = current["PACKAGE_VERSION"]
    if not re.fullmatch(
        rf"{re.escape(version)}(?:\.post[0-9]+)?", package_version
    ):
        raise ValueError("Package version does not match the bundled release")
    pyarrow = pypi_release("pyarrow", version)
    if (
        pyarrow["info"]["version"] != version
        or pyarrow["info"].get("yanked", False)
        or not any(not file.get("yanked", False) for file in pyarrow["urls"])
    ):
        raise ValueError(
            f"No usable matching PyArrow {version} release on PyPI"
        )
    checksum = arrow_checksum(version)
    pyproject_path = PROJECT_DIR / "pyproject.toml"
    pyproject = replace_once(
        pyproject_path.read_text(encoding="utf8"),
        r'^version = "[^"]+"[^\n]*$',
        f'version = "{package_version}"  # bundled Apache Arrow C++ version',
    )
    pyproject = replace_once(
        pyproject, r'^  "pyarrow [^"]+",$', f'  "pyarrow =={version}",'
    )
    tomllib.loads(pyproject)
    readme_path = PROJECT_DIR / "README.md"
    readme = replace_once(
        readme_path.read_text(encoding="utf8"),
        r"`pyarrow [^`]+`",
        f"`pyarrow =={version}`",
    )
    module = (
        '"""\ntitle: Version constants for arx-arrowcpp-sources.\n"""\n\n'
        f'PACKAGE_VERSION = "{package_version}"\n'
        f'BUNDLED_ARROWCPP_VERSION = "{version}"\n'
        'BUNDLED_ARROWCPP_TAG = f"apache-arrow-{BUNDLED_ARROWCPP_VERSION}"\n'
        f'BUNDLED_ARROWCPP_SHA256 = (\n    "{checksum}"\n)\n\n'
        "__version__ = PACKAGE_VERSION\n"
    )
    # Prepare every replacement before writing any file.
    for path, content in (
        (pyproject_path, pyproject),
        (readme_path, readme),
        (PROJECT_DIR / VERSION_MODULE, module),
    ):
        if path.read_text(encoding="utf8") != content:
            path.write_text(content, encoding="utf8")
    return package_version


def check_versions() -> None:
    """
    title: Check all local release version references.
    """
    versions = read_versions()
    bundled = versions["BUNDLED_ARROWCPP_VERSION"]
    version_tuple(bundled)
    package = versions["PACKAGE_VERSION"]
    project = tomllib.loads(
        (PROJECT_DIR / "pyproject.toml").read_text(encoding="utf8")
    )["project"]
    lock = tomllib.loads(
        (PROJECT_DIR / "poetry.lock").read_text(encoding="utf8")
    )
    pyarrow = [
        entry for entry in lock["package"] if entry["name"] == "pyarrow"
    ]
    checks = (
        project["version"] == package,
        re.fullmatch(rf"{re.escape(bundled)}(?:\.post[0-9]+)?", package)
        is not None,
        f"pyarrow =={bundled}" in project["dependencies"],
        len(pyarrow) == 1 and pyarrow[0]["version"] == bundled,
        lock["metadata"]["python-versions"] == project["requires-python"],
        re.fullmatch(r"[a-f0-9]{64}", versions["BUNDLED_ARROWCPP_SHA256"])
        is not None,
        f"`pyarrow =={bundled}`"
        in (PROJECT_DIR / "README.md").read_text(encoding="utf8"),
    )
    if not all(checks):
        raise ValueError("Versions are out of sync; run scripts/versioning.sh")


def is_published(version: str) -> bool:
    """
    title: Treat only a PyPI 404 as a not-yet-published package version.
    parameters:
      version:
        type: str
    returns:
      type: bool
    """
    try:
        release = pypi_release("arx-arrowcpp-sources", version)
    except urllib.error.HTTPError as exc:
        if exc.code == HTTPStatus.NOT_FOUND:
            return False
        raise
    if release["info"].get("yanked", False) or not release["urls"]:
        raise ValueError(f"PyPI release {version} is yanked or has no files")
    return True


def github_output(values: dict[str, str]) -> None:
    """
    title: Export validated release values to GitHub Actions.
    parameters:
      values:
        type: dict[str, str]
    """
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a", encoding="utf8") as file_handle:
            for key, value in values.items():
                file_handle.write(f"{key}={value}\n")


def main() -> None:
    """
    title: Resolve a release and refresh the Poetry lock.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", nargs="?", default="latest")
    parser.add_argument("build", nargs="?", default="")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--check-published", action="store_true")
    args = parser.parse_args()
    if args.check or args.check_published:
        check_versions()
        if args.check_published:
            published = is_published(read_versions()["PACKAGE_VERSION"])
            github_output({"published": str(published).lower()})
            print(f"Already published on PyPI: {published}")
        return
    if args.build and re.fullmatch(r"[0-9]+", args.build) is None:
        parser.error("Post-release build number must be numeric")
    version = (
        latest_arrow_version() if args.version == "latest" else args.version
    )
    package = sync_version(version, args.build)
    subprocess.run(["poetry", "lock"], cwd=PROJECT_DIR, check=True)
    check_versions()
    github_output({"version": package, "bundled_version": version})
    print(f"Release version: {package} (Apache Arrow {version})")


if __name__ == "__main__":
    main()
