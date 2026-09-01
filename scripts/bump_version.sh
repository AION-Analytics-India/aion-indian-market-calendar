#!/bin/bash
# =============================================================================
# aion-indian-market-calendar - Version Bumping Script
# =============================================================================
# Usage:
#   ./scripts/bump_version.sh <new_version>
#
# Example:
#   ./scripts/bump_version.sh 1.1.5
# =============================================================================

set -e

# Resolve script directory and package root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

NEW_VERSION="$1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

if [ -z "$NEW_VERSION" ]; then
    echo -e "${RED}Error: New version is required.${NC}"
    echo "Usage: $0 <new_version>"
    exit 1
fi

# Validate version format (e.g. 1.1.4)
if [[ ! "$NEW_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo -e "${RED}Error: Version must be in format X.Y.Z (e.g., 1.1.5)${NC}"
    exit 1
fi

echo -e "${GREEN}Bumping version to $NEW_VERSION in $PACKAGE_ROOT...${NC}"

# Define files to update
PYPROJECT_TOML="$PACKAGE_ROOT/pyproject.toml"
INIT_PY="$PACKAGE_ROOT/src/aion_indian_market_calendar/__init__.py"
DOCS_README="$PACKAGE_ROOT/publish_assets/aion-indian-market-calendar-docs/README.md"

# Determine sed -i compatibility
SED_INPLACE=(sed -i '')
if [[ "$OSTYPE" != "darwin"* ]]; then
    SED_INPLACE=(sed -i)
fi

# 1. Update pyproject.toml
if [ -f "$PYPROJECT_TOML" ]; then
    echo "Updating $PYPROJECT_TOML..."
    "${SED_INPLACE[@]}" "s/version = \"[0-9]\{1,\}\.[0-9]\{1,\}\.[0-9]\{1,\}\"/version = \"$NEW_VERSION\"/" "$PYPROJECT_TOML"
else
    echo -e "${RED}Warning: $PYPROJECT_TOML not found.${NC}"
fi

# 2. Update __init__.py fallback version
if [ -f "$INIT_PY" ]; then
    echo "Updating $INIT_PY..."
    "${SED_INPLACE[@]}" "s/__version__ = \"[0-9]\{1,\}\.[0-9]\{1,\}\.[0-9]\{1,\}\"/__version__ = \"$NEW_VERSION\"/" "$INIT_PY"
else
    echo -e "${RED}Warning: $INIT_PY not found.${NC}"
fi

# 3. Update publish_assets docs README
if [ -f "$DOCS_README" ]; then
    echo "Updating $DOCS_README..."
    "${SED_INPLACE[@]}" "s/- \*\*Version:\*\* [0-9]\{1,\}\.[0-9]\{1,\}\.[0-9]\{1,\}/- \*\*Version:\*\* $NEW_VERSION/" "$DOCS_README"
else
    echo -e "${RED}Warning: $DOCS_README not found.${NC}"
fi

echo -e "${GREEN}Version bump complete!${NC}"
