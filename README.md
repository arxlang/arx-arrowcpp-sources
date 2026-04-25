# arx-arrowcpp-sources

`arx-arrowcpp-sources` packages a pinned Apache Arrow C++ source release for the
Arx ecosystem.

It does **not** ship compiled Arrow binaries. Instead, it ships:

- the upstream Apache Arrow `cpp/` source tree
- the upstream Apache Arrow `format/` FlatBuffers definitions used by C++
- upstream release metadata, license, and notice files
- upstream `.env` configuration required by Arrow's CMake setup
- Python helper functions to locate those files from build systems

The package also depends on `pyarrow ==26.0.1` so Arx projects can use the
matching Python runtime package alongside the vendored source-release layout.

Python 3.11 or newer is required, matching the bundled release's PyArrow
support.

## Should you bundle Arrow C++ sources?

Usually, no. Prefer these integration paths when possible:

- Use an installed Arrow C++ package with CMake's `find_package(Arrow REQUIRED)`
  and link `Arrow::arrow_shared` or `Arrow::arrow_static`.
- Use `pkg-config --cflags --libs arrow` for non-CMake native builds.
- For Python-extension builds, use `pyarrow.get_include()`,
  `pyarrow.get_libraries()`, and `pyarrow.get_library_dirs()`.

This package exists for Arx workflows that need a reproducible, Python-package
addressable copy of the Arrow C++ source release.

## Usage

```python
from arx_arrowcpp_sources import (
    bundled_arrowcpp_version,
    get_cmake_dir,
    get_cpp_dir,
    get_header_files,
    get_include_dir,
    get_source_files,
)

print(bundled_arrowcpp_version())
print(get_cpp_dir())
print(get_include_dir())
print(get_cmake_dir())
print(get_header_files())
print(get_source_files())
```

## Build behavior

Run `python scripts/build_bundle.py` before `poetry build`. The bundle script
fetches the pinned Apache Arrow source release, verifies its SHA256 checksum,
and stores the C++ source subset under `src/arx_arrowcpp_sources/vendor/`.

The vendored layout is intentionally close to the upstream release layout:

```text
src/arx_arrowcpp_sources/vendor/
├── cpp/
├── format/
├── .env
├── CHANGELOG.md
├── LICENSE.txt
├── NOTICE.txt
├── README.md
└── bundle-metadata.json
```

## Development

```bash
python scripts/build_bundle.py
pytest -q
ruff check .
mypy src tests
```

## Versioning and releases

The package version follows Apache Arrow's version. Packaging-only rebuilds use
`.postN`; the bundled sources and PyArrow remain pinned to the upstream version.

```bash
# Discover the latest stable Arrow release and refresh all version pins.
bash scripts/versioning.sh latest

# Pin an upstream release, optionally with a packaging-only build number.
bash scripts/versioning.sh X.Y.Z
bash scripts/versioning.sh X.Y.Z 1

# Check consistency without accessing the network or modifying files.
bash scripts/versioning.sh --check
poetry check --lock
```

The versioning script checks that matching PyArrow files are available on PyPI,
fetches Apache's SHA256, updates `pyproject.toml`, `_version.py`, and this
README, and refreshes `poetry.lock`. It rejects prereleases, downgrades, and
invalid build numbers. Repeated runs preserve an existing `.postN` for the same
Arrow version; a newer Arrow version resets it. Commit all four synchronized
files together.

The release workflow checks upstream daily and also supports manual dispatch
with an optional Arrow version and build number. Only the default branch can
publish. New versions are tested, built, and checked from an installed wheel
before publication using the existing `PYPI_TOKEN` secret. The workflow then
commits the version files and creates a `v<package-version>` tag and GitHub
release. Already-published versions are not uploaded again; reruns can finish a
missing commit, tag, or GitHub release.

Repository settings must allow GitHub Actions to write repository contents and
push to the default branch. Branch protection that disallows bot pushes requires
an update-PR process instead.
