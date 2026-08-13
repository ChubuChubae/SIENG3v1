# Standard checks before closing a piece of work (Windows).
# Linux/macOS equivalent: scripts/check.sh · Which session runs when: docs/PROJECT_CONTEXT.md 2.6

$ErrorActionPreference = "Stop"

Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Get-Command nox -ErrorAction SilentlyContinue)) {
    Write-Error "nox not found. Install it with: pip install -e `".[dev]`""
    exit 1
}

# vectors and security gate closing a module, never skip them (PROJECT_CONTEXT.md 2.5)
nox -s lint types imports unit vectors security @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Standard checks passed."
Write-Host "Before a release also run: nox -s sast deps sbom integration fuzz_smoke"
