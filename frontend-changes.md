# Changes — Testing Framework for the RAG System

> Note: this work is backend test infrastructure (no frontend changes were
> made). The summary is written here per the `/implement-feature` slash
> command's instructions.

## What changed

Added test infrastructure for the FastAPI HTTP layer in `backend/tests/`,
configured pytest in `pyproject.toml`, and added the dev-only test
dependencies.

### Files added

- `backend/tests/__init__.py` — empty marker so the directory is importable.
- `backend/tests/conftest.py` — shared pytest fixtures (see below).
- `backend/tests/test_api.py` — endpoint tests for `/api/query`,
  `/api/courses`, and `/` (13 tests, all passing).

### Files modified

- `pyproject.toml`:
  - Added a `[dependency-groups] dev` group with `pytest>=8.3.0` and
    `httpx>=0.27.0` (httpx is required by `fastapi.testclient.TestClient`).
  - Added `[tool.pytest.ini_options]`:
    - `pythonpath = ["backend"]` — lets tests import `app`, `rag_system`,
      etc. as top-level modules (matches CLAUDE.md's described convention).
    - `testpaths = ["backend/tests"]` — pytest discovers from this root.
    - `addopts = "-ra --tb=short"` — concise failure output, show summary
      of all non-passing outcomes.
    - `filterwarnings` — suppress dependency-side deprecation noise so
      genuine test failures stand out.

## Fixtures provided by `conftest.py`

| Fixture | Purpose |
| --- | --- |
| `text_block(text)` | Factory for an Anthropic-shaped `text` content block. |
| `tool_use_block(id, name, input)` | Factory for an Anthropic-shaped `tool_use` content block. |
| `anthropic_message(content, stop_reason)` | Factory for a full `Message`-shaped object with `content`, `stop_reason`, and `usage`. Used by future `AIGenerator` tests. |
| `mock_vector_store` | `MagicMock` shaped like `VectorStore` with safe defaults (empty `SearchResults`, empty title list, count 0). Override per-test. |
| `sample_course_titles` / `sample_query_answer` / `sample_sources` | Canned values reused across endpoint tests. |
| `mock_rag_system` | `MagicMock` shaped like `RAGSystem`. `query()` returns `(answer, sources)`, `get_course_analytics()` returns the canned analytics dict, and `session_manager.create_session()` returns the deterministic id `"session_test_1"` so tests can assert on it. |
| `test_app` | A `FastAPI` app that mirrors `backend/app.py` but **skips the static-file mount and document ingestion** (both require paths that don't exist under pytest). Routes are wired against `mock_rag_system`. |
| `client` | `TestClient(test_app)`. |

### Why a separate test app

`backend/app.py` does two things at import/startup time that break test
collection:

1. Mounts `../frontend` as static files (path resolved from the launch dir,
   not the test working dir).
2. Ingests `../docs` in an `@app.on_event("startup")` handler.

Rather than monkey-patch around both, the `test_app` fixture rebuilds the
same routes inline using the same Pydantic request/response models. The
models are defined at module scope in `conftest.py` — defining them inside
the fixture closure caused FastAPI's type-hint resolution to misclassify
the body parameter as a query parameter (verified by reproducing the
`422 / loc:["query","request"]` failure).

## Endpoint tests (`test_api.py`)

Grouped into classes by endpoint:

### `TestQueryEndpoint` — `POST /api/query`
- Returns the expected `answer`, `sources`, and `session_id` shape.
- Auto-creates a session id when none is supplied and forwards it to
  `RAGSystem.query`.
- Reuses a caller-supplied `session_id` without creating a new one.
- A missing `query` field returns 422 (pydantic validation).
- A raised exception in `RAGSystem.query` surfaces as a 500 with the
  message in `detail` (matches the production handler).
- Empty `sources` serialize as `[]`, not `null`.

### `TestCoursesEndpoint` — `GET /api/courses`
- Returns `total_courses` and `course_titles` from analytics.
- Handles an empty catalog cleanly.
- Surfaces analytics exceptions as 500.

### `TestRootEndpoint` — `GET /`
- Returns a JSON status payload (the test app's stand-in for the static
  mount that production uses at `/`).

### `TestContentTypeAndShape`
- Parametrized check that all endpoints return `application/json`.

## How to run

```bash
uv sync --dev          # one-time, installs pytest + httpx
uv run pytest          # 13 passed in ~0.3s
uv run pytest backend/tests/test_api.py::TestQueryEndpoint
```

## Verification

```
backend\tests\test_api.py .............                                  [100%]
============================= 13 passed in 0.30s ==============================
```
---

# Frontend Changes — Code Quality Tooling

Adds essential code-quality tooling to the **frontend** (`frontend/*.html|css|js`) workflow,
without touching the Python backend.

## Scope

The original feature ask named `black` (a Python-only formatter). Because the task is
scoped to **front-end features only**, `black` does not apply — there is no Python in
`frontend/`. The frontend equivalent is **Prettier**, which formats HTML, CSS, and JS
under one tool, mirroring what `black` does for Python.

## New / modified files

### Added

| Path | Purpose |
| --- | --- |
| `.prettierrc.json` | Prettier config (4-space indent, single quotes, 100-col print width, LF line endings, `es5` trailing commas, JSON/YAML/MD overrides at 2-space). |
| `.prettierignore` | Excludes `backend/`, `node_modules/`, lockfiles, ChromaDB data, env files, and `frontend-changes.md` from formatting. |
| `package.json` | Declares `prettier ^3.3.3` as a dev dependency and exposes `npm run format`, `format:check`, `format:frontend`, `quality`. Marked `private: true` — never published. |
| `package-lock.json` | Auto-generated by `npm install` to pin the Prettier version. |
| `scripts/format.sh` | Bash helper: installs deps if missing, then runs `prettier --write` on the frontend. |
| `scripts/format-check.sh` | Bash helper: CI-style `prettier --check` on the frontend (non-zero exit on drift). |
| `scripts/quality.sh` | Bash entry point: runs all frontend quality checks (currently format-check). Extension point for future linters. |
| `scripts/format.ps1` | PowerShell parity of `format.sh` for Windows users. |
| `scripts/format-check.ps1` | PowerShell parity of `format-check.sh`. |
| `scripts/quality.ps1` | PowerShell parity of `quality.sh`. |

### Modified

| Path | Change |
| --- | --- |
| `.gitignore` | Appended `node_modules/` and npm debug log patterns so frontend tooling does not pollute the repo. |
| `frontend/index.html` | Reformatted by Prettier — consistent attribute wrapping, indentation, and trailing newlines. No semantic / DOM changes. |
| `frontend/script.js` | Reformatted by Prettier — removed trailing whitespace, normalized quote / spacing / semicolon style. No behavior changes. |
| `frontend/style.css` | Reformatted by Prettier — consistent rule spacing, one-declaration-per-line, multi-selector breakout (e.g. `0%, 80%, 100%` keyframe stops on separate lines). No visual changes. |

## Prettier configuration (`.prettierrc.json`)

```json
{
    "tabWidth": 4,
    "useTabs": false,
    "semi": true,
    "singleQuote": true,
    "printWidth": 100,
    "trailingComma": "es5",
    "arrowParens": "always",
    "endOfLine": "lf",
    "bracketSpacing": true,
    "htmlWhitespaceSensitivity": "css",
    "overrides": [
        { "files": "*.md", "options": { "tabWidth": 2, "proseWrap": "preserve" } },
        { "files": ["*.json", "*.yml", "*.yaml"], "options": { "tabWidth": 2 } }
    ]
}
```

Rationale for the non-defaults:

- **`tabWidth: 4`** matches the existing frontend indent; switching to 2 would have
  produced a large gratuitous diff with no readability win.
- **`singleQuote: true`** matches the JS already in `script.js`.
- **`printWidth: 100`** gives long HTML attributes (e.g. the suggested-question buttons)
  room without forcing them onto a single multi-line block.
- **`endOfLine: "lf"`** keeps line endings stable across Windows/macOS/Linux
  contributors and CI.
- **Override for `*.md` / `*.json` / `*.yml`** drops to 2-space indent — the universal
  convention for those formats.

## npm scripts (`package.json`)

| Script | What it does |
| --- | --- |
| `npm run format` | Rewrites every frontend file + top-level `*.md` / `*.json` in place. |
| `npm run format:frontend` | Same as above but only `frontend/**`. |
| `npm run format:check` | Reports drift without modifying files (exits 1 on drift). |
| `npm run quality` | Aggregates the quality gate. Currently delegates to `format:check`; new linters slot in here. |

## Standalone scripts (`scripts/`)

For contributors who prefer not to remember npm script names, or for CI / git hooks:

- **Bash:** `scripts/format.sh`, `scripts/format-check.sh`, `scripts/quality.sh`
- **PowerShell:** `scripts/format.ps1`, `scripts/format-check.ps1`, `scripts/quality.ps1`

Each script:

1. `cd`s to the repo root regardless of invocation directory.
2. Runs `npm install` automatically if `node_modules/` is missing (so a fresh clone
   works on the first invocation).
3. Invokes `npx prettier` with the appropriate mode.

## How a developer uses this

```bash
# One-time setup (or after pulling new deps):
npm install

# Format everything before committing:
npm run format
# …or, equivalently:
bash scripts/format.sh
# Windows:
pwsh scripts/format.ps1

# Verify formatting without writing (use in CI / pre-push):
npm run quality
# …or:
bash scripts/quality.sh
```

## Verification performed

1. `npx prettier --check "frontend/**/*.{js,css,html}"` → 3 files needed formatting.
2. `npx prettier --write "frontend/**/*.{js,css,html}"` → wrote all 3.
3. `npx prettier --check ...` again → **"All matched files use Prettier code style!"**
4. `bash scripts/format-check.sh` → exits 0 cleanly, confirms script wiring works.

## Out of scope (intentionally)

- **Python backend** (`backend/**`, `main.py`) — task is frontend-only. Adding `black`
  to the Python side is a separate change.
- **ESLint / Stylelint** — only formatting was requested. Linters can be added later
  under the `npm run quality` umbrella without breaking the existing wiring.
- **Pre-commit hooks** — not requested. The `scripts/quality.sh` entry point is the
  natural place to mount one (e.g. via `husky` or `pre-commit`) if desired.
