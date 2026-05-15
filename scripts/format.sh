#!/usr/bin/env bash
# Auto-format frontend sources (HTML / CSS / JS) with Prettier.
# Run from the repo root.

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -d node_modules ]; then
    echo "[format] node_modules missing — running npm install first..."
    npm install --no-audit --no-fund
fi

echo "[format] Running prettier --write on frontend/..."
npx prettier --write "frontend/**/*.{js,css,html}" "$@"

echo "[format] Done."
