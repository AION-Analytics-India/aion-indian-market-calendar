#!/bin/bash
# =============================================================================
# AION Indian Market Calendar - Release Readiness Verifier
# =============================================================================
# This script enforces the following invariant checks:
# 1. Scans files to ensure no forbidden 'projects/' imports exist.
# 2. If a git tag is provided, checks that it matches the pyproject.toml version.
# 3. Runs the test suite to ensure clean tests.
# 4. Compiles the package to verify the build succeeds.
# 5. Installs the compiled wheel in a clean env and verifies import sanity.
# =============================================================================

set -e

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Parse tag argument if provided
EXPECTED_VERSION=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            TAG_VAL="$2"
            # Remove 'v' prefix if present
            EXPECTED_VERSION="${TAG_VAL#v}"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 [--tag vX.Y.Z]"
            exit 1
            ;;
    esac
done

# If no tag argument but running in GHA / GitLab CI, try to load from environment
if [ -z "$EXPECTED_VERSION" ]; then
    if [ ! -z "$GITHUB_REF_NAME" ] && [[ "$GITHUB_REF_NAME" =~ ^v[0-9] ]]; then
        EXPECTED_VERSION="${GITHUB_REF_NAME#v}"
    elif [ ! -z "$CI_COMMIT_TAG" ] && [[ "$CI_COMMIT_TAG" =~ ^v[0-9] ]]; then
        EXPECTED_VERSION="${CI_COMMIT_TAG#v}"
    fi
fi

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

cd "$PACKAGE_ROOT"

# -----------------------------------------------------------------------------
# Check 1: No 'projects/' or 'projects.aion_indian_market_calendar' imports
# -----------------------------------------------------------------------------
log_info "Check 1/5: Scanning for forbidden 'projects/' imports..."

# Check source files and tests for projects.aion_indian_market_calendar, excluding __pycache__ and test_firewall.py
if grep -rn --exclude-dir="__pycache__" --exclude="test_firewall.py" "projects\.aion_indian_market_calendar" src/ tests/ > /dev/null 2>&1; then
    log_error "Forbidden reference 'projects.aion_indian_market_calendar' found!"
    grep -rn --exclude-dir="__pycache__" --exclude="test_firewall.py" "projects\.aion_indian_market_calendar" src/ tests/
    exit 1
fi

# Check source files for 'projects/' (except projects/archive or similar safe paths), excluding __pycache__
VIOLATIONS=$(grep -rn --exclude-dir="__pycache__" "projects/" src/ | grep -v "projects/archive" || true)
if [ ! -z "$VIOLATIONS" ]; then
    log_error "OSS boundary violation! Production code contains references to projects/:"
    echo "$VIOLATIONS"
    exit 1
fi

log_info "✓ Import firewall clean."

# -----------------------------------------------------------------------------
# Check 2: Version matches Git Tag (if tag is provided)
# -----------------------------------------------------------------------------
log_info "Check 2/5: Verifying package version..."

PYPROJECT_VERSION=$(python3 -c "
import tomli
with open('pyproject.toml', 'rb') as f:
    print(tomli.load(f)['project']['version'])
" 2>/dev/null || python3 -c "
import json
# Fallback to simple parser if tomli is not installed
for line in open('pyproject.toml'):
    if line.strip().startswith('version ='):
        print(line.split('=')[1].strip().strip('\"').strip('\''))
        break
" 2>/dev/null)

if [ -z "$PYPROJECT_VERSION" ]; then
    log_error "Could not parse version from pyproject.toml"
    exit 1
fi

log_info "Found pyproject.toml version: $PYPROJECT_VERSION"

if [ ! -z "$EXPECTED_VERSION" ]; then
    if [ "$PYPROJECT_VERSION" != "$EXPECTED_VERSION" ]; then
        log_error "Version mismatch! pyproject.toml version ($PYPROJECT_VERSION) does not match expected tag version ($EXPECTED_VERSION)"
        exit 1
    else
        log_info "✓ Version matches expected tag version ($EXPECTED_VERSION)."
    fi
else
    log_info "No tag specified/detected. Skipping tag version match check."
fi

# -----------------------------------------------------------------------------
# Check 3: Clean Tests
# -----------------------------------------------------------------------------
log_info "Check 3/5: Running regression test suite..."

# Use virtualenv pytest if available, otherwise fallback to system pytest
PYTEST_BIN="pytest"
if [ -f "$PACKAGE_ROOT/../../venv/bin/pytest" ]; then
    PYTEST_BIN="$PACKAGE_ROOT/../../venv/bin/pytest"
fi

PYTHONPATH=src "$PYTEST_BIN" tests/ -q --tb=short
if [ $? -ne 0 ]; then
    log_error "Regression test suite failed."
    exit 1
fi
log_info "✓ Test suite passed."

# -----------------------------------------------------------------------------
# Check 4: Build succeeds
# -----------------------------------------------------------------------------
log_info "Check 4/5: Compiling python build package..."

# Clean old dist
rm -rf dist/ build/ *.egg-info

python3 -m build > /dev/null 2>&1
if [ $? -ne 0 ]; then
    log_error "Package build compilation failed."
    exit 1
fi

WHEEL=$(ls dist/*.whl 2>/dev/null | head -1)
if [ -z "$WHEEL" ]; then
    log_error "No wheel file was compiled."
    exit 1
fi
log_info "✓ Build succeeded: $(basename "$WHEEL")"

# -----------------------------------------------------------------------------
# Check 5: Import sanity check passes
# -----------------------------------------------------------------------------
log_info "Check 5/5: Running post-build import sanity check..."

python3 -m venv test_env
test_env/bin/pip install --upgrade pip
test_env/bin/pip install --force-reinstall "$WHEEL"

IMPORTED_VERSION=$(test_env/bin/python3 -c "
import aion_indian_market_calendar
print(aion_indian_market_calendar.__version__)
")

rm -rf test_env

if [ "$IMPORTED_VERSION" != "$PYPROJECT_VERSION" ]; then
    log_error "Import sanity check failed! Imported version ($IMPORTED_VERSION) does not match build version ($PYPROJECT_VERSION)"
    exit 1
fi

log_info "✓ Import sanity check passed successfully."
log_info "========================================================================="
log_info "🎉 RELEASE VALIDATION SUCCESSFUL: Package is 100% ready for PyPI publish!"
log_info "========================================================================="
