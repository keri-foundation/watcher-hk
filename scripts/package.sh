#!/bin/bash
# Build and publish witopnet to PyPI.
#
# Requirements:
#   pip install build twine
#
# Usage:
#   ./scripts/package.sh           # publish to PyPI
#   ./scripts/package.sh --test    # publish to TestPyPI (for validation)
set -euo pipefail

REPO_FLAG=""
if [[ "${1:-}" == "--test" ]]; then
    REPO_FLAG="--repository testpypi"
    echo "Target: TestPyPI"
else
    echo "Target: PyPI"
fi

echo "Cleaning previous builds..."
rm -rf dist/ build/ src/*.egg-info

echo "Building source distribution and wheel..."
python -m build

echo "Uploading..."
# shellcheck disable=SC2086
twine upload $REPO_FLAG dist/*