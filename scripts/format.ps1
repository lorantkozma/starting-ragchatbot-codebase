#!/usr/bin/env pwsh
# Auto-format frontend sources (HTML / CSS / JS) with Prettier (Windows / PowerShell).

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

if (-not (Test-Path node_modules)) {
    Write-Host '[format] node_modules missing - running npm install first...'
    npm install --no-audit --no-fund
}

Write-Host '[format] Running prettier --write on frontend/...'
npx prettier --write "frontend/**/*.{js,css,html}" @args
Write-Host '[format] Done.'
