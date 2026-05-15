#!/usr/bin/env pwsh
# Verify frontend sources are correctly formatted (CI-style, Windows / PowerShell).

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Test-Path node_modules)) {
    Write-Host '[format-check] node_modules missing - running npm install first...'
    npm install --no-audit --no-fund
}

Write-Host '[format-check] Running prettier --check on frontend/...'
npx prettier --check "frontend/**/*.{js,css,html}" @args
