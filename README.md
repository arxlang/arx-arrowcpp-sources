# arx-arrowcpp-sources

`arx-arrowcpp-sources` packages a pinned Apache Arrow C++ source release for
the Arx ecosystem.

It does **not** ship compiled Arrow binaries. Instead, it ships:

- the upstream Apache Arrow `cpp/` source tree
- the upstream Apache Arrow `format/` FlatBuffers definitions used by C++
- upstream release metadata, license, and notice files
- Python helper functions to locate those files from build systems

The package also depends on `pyarrow >=24.0.0,<25.0.0` so Arx projects can use
the matching Python runtime package alongside the vendored source-release
layout.

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
