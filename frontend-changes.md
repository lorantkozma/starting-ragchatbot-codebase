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
