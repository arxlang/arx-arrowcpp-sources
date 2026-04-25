"""
title: Offline regression tests for Arrow release synchronization.
"""

from __future__ import annotations

import json
import shutil
import sys
import tomllib
import urllib.error

from email.message import Message
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from scripts import versioning

PROJECT_DIR = Path(__file__).resolve().parent.parent
CHECKSUM = "a" * 64
NEXT_VERSION = "27.0.0"


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    title: Copy versioned files into an isolated project.
    parameters:
      tmp_path:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    returns:
      type: Path
    """
    for name in (
        "pyproject.toml",
        "poetry.lock",
        "README.md",
        versioning.VERSION_MODULE,
    ):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(PROJECT_DIR / name, target)
    monkeypatch.setattr(versioning, "PROJECT_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def upstream(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """
    title: Provide a matching non-yanked PyArrow and Apache checksum.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
    returns:
      type: Mock
    """
    metadata = Mock(
        return_value={
            "info": {"version": NEXT_VERSION, "yanked": False},
            "urls": [{"yanked": False}],
        }
    )
    monkeypatch.setattr(versioning, "pypi_release", metadata)
    monkeypatch.setattr(
        versioning, "arrow_checksum", Mock(return_value=CHECKSUM)
    )
    return metadata


def snapshot(project: Path) -> dict[Path, bytes]:
    """
    title: Capture files to detect partial edits on failure.
    parameters:
      project:
        type: Path
    returns:
      type: dict[Path, bytes]
    """
    return {
        path: path.read_bytes()
        for path in project.rglob("*")
        if path.is_file()
    }


def test_current_versions_are_synchronized() -> None:
    """
    title: Keep committed release references synchronized in CI.
    """
    versioning.check_versions()


def test_sync_updates_all_pins(project: Path, upstream: Mock) -> None:
    """
    title: Synchronize sources, package, dependency, checksum and docs.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
    """
    assert (
        versioning.sync_version(NEXT_VERSION, "01") == f"{NEXT_VERSION}.post1"
    )
    upstream.assert_called_once_with("pyarrow", NEXT_VERSION)
    constants = versioning.read_versions()
    assert constants["PACKAGE_VERSION"] == f"{NEXT_VERSION}.post1"
    assert constants["BUNDLED_ARROWCPP_VERSION"] == NEXT_VERSION
    assert constants["BUNDLED_ARROWCPP_SHA256"] == CHECKSUM
    project_data = tomllib.loads((project / "pyproject.toml").read_text())
    assert project_data["project"]["version"] == f"{NEXT_VERSION}.post1"
    assert project_data["project"]["dependencies"] == [
        f"pyarrow =={NEXT_VERSION}"
    ]
    assert f"`pyarrow =={NEXT_VERSION}`" in (project / "README.md").read_text()
    # The CLI must refresh the old lock before a release is allowed.
    with pytest.raises(ValueError, match="out of sync"):
        versioning.check_versions()


def test_repeated_sync_preserves_post_release(
    project: Path, upstream: Mock
) -> None:
    """
    title: Never reset a post-release on the next scheduled check.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
    """
    versioning.sync_version(NEXT_VERSION, "2")
    before = snapshot(project)
    assert versioning.sync_version(NEXT_VERSION) == f"{NEXT_VERSION}.post2"
    assert snapshot(project) == before


def test_new_upstream_resets_post_release(
    project: Path, upstream: Mock
) -> None:
    """
    title: Start a fresh package version for the next Arrow release.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
    """
    versioning.sync_version(NEXT_VERSION, "2")
    upstream.return_value["info"]["version"] = "27.0.1"
    assert versioning.sync_version("27.0.1") == "27.0.1"


@pytest.mark.parametrize(
    "version", ["v27.0.0", "27.0.0rc1", "27.0", "27.0.0\n", "027.0.0"]
)
def test_invalid_version_leaves_files_untouched(
    project: Path, upstream: Mock, version: str
) -> None:
    """
    title: Reject noncanonical or prerelease versions before fetching.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
      version:
        type: str
    """
    before = snapshot(project)
    with pytest.raises(ValueError, match="stable Arrow"):
        versioning.sync_version(version)
    assert snapshot(project) == before
    upstream.assert_not_called()


@pytest.mark.parametrize("build", ["-1", "1.0", "1\n", "oops"])
def test_invalid_build_leaves_files_untouched(
    project: Path, upstream: Mock, build: str
) -> None:
    """
    title: Reject malformed post-release build numbers.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
      build:
        type: str
    """
    before = snapshot(project)
    with pytest.raises(ValueError, match="numeric"):
        versioning.sync_version(NEXT_VERSION, build)
    assert snapshot(project) == before
    upstream.assert_not_called()


def test_downgrade_is_rejected(project: Path, upstream: Mock) -> None:
    """
    title: Never release older bundled Arrow sources by accident.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
    """
    with pytest.raises(ValueError, match="downgrade"):
        versioning.sync_version("1.0.0")
    upstream.assert_not_called()


@pytest.mark.parametrize(
    "invalid", ["yanked", "empty", "all_yanked", "wrong_version"]
)
def test_unavailable_pyarrow_does_not_edit_files(
    project: Path, upstream: Mock, invalid: str
) -> None:
    """
    title: Require an available matching PyArrow before editing metadata.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
      invalid:
        type: str
    """
    data = upstream.return_value
    if invalid == "yanked":
        data["info"]["yanked"] = True
    elif invalid == "empty":
        data["urls"] = []
    elif invalid == "all_yanked":
        data["urls"] = [{"yanked": True}]
    else:
        data["info"]["version"] = "1.0.0"
    before = snapshot(project)
    with pytest.raises(ValueError, match="matching PyArrow"):
        versioning.sync_version(NEXT_VERSION)
    assert snapshot(project) == before


def test_missing_reference_prevents_partial_edits(
    project: Path, upstream: Mock
) -> None:
    """
    title: Fail if documentation has lost its synchronized reference.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
    """
    (project / "README.md").write_text("No version reference here.\n")
    before = snapshot(project)
    with pytest.raises(ValueError, match="exactly one"):
        versioning.sync_version(NEXT_VERSION)
    assert snapshot(project) == before


def test_latest_version_is_stable_and_sorted_numerically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Ignore release candidates and sort 10 after 9.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    read = Mock(
        return_value="""
        <a href="arrow-9.0.0/">9</a>
        <a href="arrow-10.0.1/">10</a>
        <a href="arrow-10.0.0/">10</a>
        <a href="arrow-11.0.0-rc1/">rc</a>
        <a href="arrow-11.0.0.dev/">dev</a>
        <a href="arrow-011.0.0/">invalid</a>
    """
    )
    monkeypatch.setattr(versioning, "read_url", read)
    assert versioning.latest_arrow_version() == "10.0.1"
    read.assert_called_once_with(versioning.APACHE_DOWNLOADS)


def test_latest_discovery_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Refuse to guess if Apache's index cannot be parsed.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.setattr(
        versioning, "read_url", Mock(return_value="No releases")
    )
    with pytest.raises(ValueError, match="no stable releases"):
        versioning.latest_arrow_version()


@pytest.mark.parametrize("archived", [False, True])
def test_checksum_resolution(
    monkeypatch: pytest.MonkeyPatch, archived: bool
) -> None:
    """
    title: Accept Apache checksum files and fall back to the archive.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
      archived:
        type: bool
    """
    checksum = f"{CHECKSUM}  apache-arrow-{NEXT_VERSION}.tar.gz\n"
    responses: list[Any] = [checksum]
    if archived:
        responses.insert(0, urllib.error.URLError("retired release"))
    read = Mock(side_effect=responses)
    monkeypatch.setattr(versioning, "read_url", read)
    assert versioning.arrow_checksum(NEXT_VERSION) == CHECKSUM
    base = (
        versioning.APACHE_ARCHIVE if archived else versioning.APACHE_DOWNLOADS
    )
    read.assert_called_with(
        f"{base}arrow-{NEXT_VERSION}/apache-arrow-{NEXT_VERSION}.tar.gz.sha256"
    )


@pytest.mark.parametrize("checksum", ["bad", f"{'a' * 64}  wrong.tar.gz"])
def test_invalid_checksum_is_rejected(
    monkeypatch: pytest.MonkeyPatch, checksum: str
) -> None:
    """
    title: Never accept an invalid checksum or another archive's hash.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
      checksum:
        type: str
    """
    monkeypatch.setattr(versioning, "read_url", Mock(return_value=checksum))
    with pytest.raises(ValueError, match="Invalid Apache SHA256"):
        versioning.arrow_checksum(NEXT_VERSION)


@pytest.mark.parametrize(
    "status",
    [
        HTTPStatus.NOT_FOUND,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.INTERNAL_SERVER_ERROR,
    ],
)
def test_publication_check_only_accepts_404(
    monkeypatch: pytest.MonkeyPatch, status: HTTPStatus
) -> None:
    """
    title: Do not confuse network or authorization errors with absence.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
      status:
        type: HTTPStatus
    """
    error = urllib.error.HTTPError(
        "https://pypi.org/", status, "error", Message(), None
    )
    monkeypatch.setattr(versioning, "pypi_release", Mock(side_effect=error))
    if status == HTTPStatus.NOT_FOUND:
        assert not versioning.is_published(NEXT_VERSION)
    else:
        with pytest.raises(urllib.error.HTTPError):
            versioning.is_published(NEXT_VERSION)


def test_publication_check_skips_existing_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Skip uploads of an existing usable release.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.setattr(
        versioning,
        "pypi_release",
        Mock(return_value={"info": {}, "urls": [{}]}),
    )
    assert versioning.is_published(NEXT_VERSION)


@pytest.mark.parametrize(
    "data",
    [{"info": {"yanked": True}, "urls": [{}]}, {"info": {}, "urls": []}],
)
def test_unusable_publication_is_an_error(
    monkeypatch: pytest.MonkeyPatch, data: dict[str, Any]
) -> None:
    """
    title: Do not attempt to overwrite a yanked or empty PyPI release.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
      data:
        type: dict[str, Any]
    """
    monkeypatch.setattr(versioning, "pypi_release", Mock(return_value=data))
    with pytest.raises(ValueError, match="yanked or has no files"):
        versioning.is_published(NEXT_VERSION)


def test_cli_refreshes_lock_and_exports_version(
    project: Path, upstream: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Refresh the lock before exposing a version to the release job.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.setattr(sys, "argv", ["versioning.py", "latest", "1"])
    monkeypatch.setattr(
        versioning, "latest_arrow_version", Mock(return_value=NEXT_VERSION)
    )
    lock = Mock()
    check = Mock()
    monkeypatch.setattr("scripts.versioning.subprocess.run", lock)
    monkeypatch.setattr(versioning, "check_versions", check)
    output = project / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    versioning.main()
    lock.assert_called_once_with(["poetry", "lock"], cwd=project, check=True)
    check.assert_called_once_with()
    assert (
        output.read_text()
        == f"version={NEXT_VERSION}.post1\nbundled_version={NEXT_VERSION}\n"
    )


def test_check_mode_is_offline(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Check mode must neither access the network nor change files.
    parameters:
      project:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    read = Mock(side_effect=AssertionError("unexpected network access"))
    lock = Mock(side_effect=AssertionError("unexpected lock refresh"))
    monkeypatch.setattr(versioning, "read_url", read)
    monkeypatch.setattr("scripts.versioning.subprocess.run", lock)
    monkeypatch.setattr(sys, "argv", ["versioning.py", "--check"])
    before = snapshot(project)
    versioning.main()
    assert snapshot(project) == before


def test_pypi_metadata_uses_exact_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    title: Query a specific PyArrow version rather than its latest alias.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    read = Mock(return_value=json.dumps({"info": {"version": NEXT_VERSION}}))
    monkeypatch.setattr(versioning, "read_url", read)
    assert (
        versioning.pypi_release("pyarrow", NEXT_VERSION)["info"]["version"]
        == NEXT_VERSION
    )
    read.assert_called_once_with(
        f"{versioning.PYPI}pyarrow/{NEXT_VERSION}/json"
    )


def test_post_release_downgrade_is_rejected(
    project: Path, upstream: Mock
) -> None:
    """
    title: Refuse to move a published package back to an older post build.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
    """
    versioning.sync_version(NEXT_VERSION, "2")
    before = snapshot(project)
    with pytest.raises(ValueError, match="downgrade"):
        versioning.sync_version(NEXT_VERSION, "1")
    assert snapshot(project) == before


@pytest.mark.parametrize(
    "data",
    [{"info": {"yanked": True}, "urls": [{}]}, {"info": {}, "urls": []}],
)
def test_unusable_existing_release_is_rejected(
    monkeypatch: pytest.MonkeyPatch, data: dict[str, Any]
) -> None:
    """
    title: Refuse to republish a yanked or empty PyPI release.
    parameters:
      monkeypatch:
        type: pytest.MonkeyPatch
      data:
        type: dict[str, Any]
    """
    monkeypatch.setattr(versioning, "pypi_release", Mock(return_value=data))
    with pytest.raises(ValueError, match="yanked or has no files"):
        versioning.is_published(NEXT_VERSION)


def test_published_mode_exports_skip_decision(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Export the skip flag used by the release workflow.
    parameters:
      project:
        type: Path
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.setattr(sys, "argv", ["versioning.py", "--check-published"])
    published = Mock(return_value=True)
    monkeypatch.setattr(versioning, "is_published", published)
    output = project / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    versioning.main()
    published.assert_called_once_with(
        versioning.read_versions()["PACKAGE_VERSION"]
    )
    assert output.read_text() == "published=true\n"


def test_lock_failure_does_not_export_release_version(
    project: Path, upstream: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    title: Do not allow publication if dependency resolution fails.
    parameters:
      project:
        type: Path
      upstream:
        type: Mock
      monkeypatch:
        type: pytest.MonkeyPatch
    """
    monkeypatch.setattr(sys, "argv", ["versioning.py", NEXT_VERSION])
    monkeypatch.setattr(
        "scripts.versioning.subprocess.run",
        Mock(side_effect=RuntimeError("lock failed")),
    )
    output = project / "outputs"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    with pytest.raises(RuntimeError, match="lock failed"):
        versioning.main()
    assert not output.exists()
