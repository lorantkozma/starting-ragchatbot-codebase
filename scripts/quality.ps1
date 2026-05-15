#!/usr/bin/env pwsh
# Run all frontend quality checks (Windows / PowerShell).

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')

Write-Host '[quality] === Frontend quality checks ==='
pwsh -File scripts/format-check.ps1
Write-Host '[quality] All checks passed.'
