#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && cd .. && pwd )"

if [ "${1:-}" = "" ]; then
  echo "Bundled Apache Arrow C++ version parameter is required."
  exit 1
fi

BUNDLED_VERSION="$1"
BUILD_NUM="${2:-}"
PACKAGE_VERSION="$BUNDLED_VERSION"

if [[ -n "$BUILD_NUM" ]]; then
  if [[ ! "$BUILD_NUM" =~ ^[0-9]+$ ]]; then
    echo "[EE] BUILD_NUM must be numeric, got: $BUILD_NUM" >&2
    exit 1
  fi

  PACKAGE_VERSION="${BUNDLED_VERSION}.post${BUILD_NUM}"
fi

PYPROJECT_PATH="${PROJECT_DIR}/pyproject.toml"
VERSION_MODULE_PATH="${PROJECT_DIR}/src/arx_arrowcpp_sources/_version.py"

sed -Ei \
  's@^(version[[:space:]]*=[[:space:]]*")([^"]+)("([[:space:]]*#.*bundled Apache Arrow C\+\+ version.*))$@\1'"$PACKAGE_VERSION"'\3@' \
  "${PYPROJECT_PATH}"

sed -Ei \
  's@^(PACKAGE_VERSION[[:space:]]*=[[:space:]]*")([^"]+)(")$@\1'"$PACKAGE_VERSION"'\3@' \
  "${VERSION_MODULE_PATH}"

sed -Ei \
  's@^(BUNDLED_ARROWCPP_VERSION[[:space:]]*=[[:space:]]*")([^"]+)(")$@\1'"$BUNDLED_VERSION"'\3@' \
  "${VERSION_MODULE_PATH}"
