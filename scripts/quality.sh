#!/usr/bin/env bash
# Run all frontend quality checks. Currently: prettier format check.
# Extend this script as new linters are added.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "[quality] === Frontend quality checks ==="
bash scripts/format-check.sh
echo "[quality] All checks passed."
