#!/usr/bin/env bash
# Verify frontend sources are correctly formatted (CI-style).
# Exits non-zero if any file would be reformatted by Prettier.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d node_modules ]; then
    echo "[format-check] node_modules missing — running npm install first..."
    npm install --no-audit --no-fund
fi

echo "[format-check] Running prettier --check on frontend/..."
npx prettier --check "frontend/**/*.{js,css,html}" "$@"
