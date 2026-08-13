#!/usr/bin/env bash
# Standard checks before closing a piece of work (Linux / macOS).
# Windows equivalent: scripts/check.ps1 · Which session runs when: docs/PROJECT_CONTEXT.md 2.6

set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v nox >/dev/null 2>&1; then
    echo "nox not found. Install it with: pip install -e \".[dev]\"" >&2
    exit 1
fi

# vectors and security gate closing a module, never skip them (PROJECT_CONTEXT.md 2.5)
nox -s lint types imports unit vectors security "$@"

echo
echo "Standard checks passed."
echo "Before a release also run: nox -s sast deps sbom integration fuzz_smoke"
