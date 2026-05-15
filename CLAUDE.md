# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Run the application

The server **must** be launched from `backend/` because `app.py` uses the relative paths `../docs` (startup ingestion) and `../frontend` (static mount).

```bash
# From repo root, via the helper script (Bash / Git Bash):
./run.sh

# Or manually (works in PowerShell):
cd backend
uv run uvicorn app:app --reload --port 8000
```

App at http://localhost:8000, OpenAPI docs at http://localhost:8000/docs.

### Dependencies

```bash
uv sync          # install / refresh from uv.lock
```

Python 3.13+ is required (`pyproject.toml`, `.python-version`). Use `uv` for everything — there is no `pip`/`requirements.txt` workflow and no `Makefile`.

### Configuration

Create `.env` at repo root with `ANTHROPIC_API_KEY=...`. Loaded by `backend/config.py` via `python-dotenv`. A missing/empty key does not fail at boot — it fails on the first `/api/query` call.

### Tests

```bash
uv run pytest                                   # whole suite
uv run pytest backend/tests/test_ai_generator.py        # one file
uv run pytest backend/tests/test_ai_generator.py::test_name  # one test
```

`pyproject.toml` sets `pythonpath = ["backend"]` and `testpaths = ["backend/tests"]`, so tests import backend modules as top-level (`from ai_generator import ...`), not as `backend.ai_generator`. Mirror that when adding tests. Shared fixtures live in `backend/tests/conftest.py` (Anthropic response/content-block factories, a `VectorStore` MagicMock). No linter or formatter is configured — don't invent one.

## Architecture

This is a **tool-using RAG** chatbot: rather than always prepending retrieved chunks to the prompt, Claude is given tools and decides whether (and which) to call. Two tools are registered: `search_course_content` (chunk retrieval) and `get_course_outline` (course title + link + lesson list). The system prompt caps usage at **two sequential tool rounds per query**.

### Request lifecycle

A `POST /api/query` results in **up to three Claude API calls** (2 tool-enabled rounds + 1 forced final call):

1. `app.py:query_documents` → `RAGSystem.query()` (`backend/rag_system.py:104`).
2. `AIGenerator.generate_response()` enters `_run_tool_loop` when `tools` and `tool_manager` are both passed. Each iteration:
   - Calls Claude with `tools=[...]` and `tool_choice=auto`.
   - If `stop_reason != "tool_use"` → return its text now (exit **b**).
   - Otherwise dispatch every `tool_use` block through `ToolManager.execute_tool`, append the assistant turn + `tool_result` user turn to `messages`, loop.
3. Termination conditions (see `_run_tool_loop`):
   - **(a)** `MAX_TOOL_ROUNDS = 2` reached → one final Claude call **without tools** produces the answer text.
   - **(b)** Claude returns a turn with no `tool_use` blocks → return that text directly.
   - **(c)** Any tool raised — the exception is captured as `is_error: True` in the tool_result and the loop bails to a forced no-tools final call so Claude can phrase the failure.
4. `_extract_text` scans `response.content` for the first `text` block (guards against responses whose first block is `tool_use`/empty — don't replace it with `content[0].text`).

Implication: do not assume there's a single round, and do not call Claude with `tools=` after the cap — that would let it loop forever. The forced no-tools call is the safety net.

### Two ChromaDB collections

`VectorStore` (`backend/vector_store.py`) maintains two collections backed by `all-MiniLM-L6-v2` embeddings, persisted at `backend/chroma_db/`:

- **`course_catalog`** — one row per course (title is the primary ID). Used for **fuzzy course-name resolution**: when the tool gets `course_name="MCP"`, it does a 1-result vector query here to find the canonical title before filtering content.
- **`course_content`** — one row per chunk, with `course_title` / `lesson_number` / `chunk_index` metadata. The actual retrieval target.

### Sources side channel

`CourseSearchTool` stashes the source list of its last search on `self.last_sources`, as a list of `{"text": "<course> - Lesson N", "link": <lesson url or None>}` dicts (link looked up via `VectorStore.get_lesson_link`). `RAGSystem.query()` reads it via `ToolManager.get_last_sources()` **after** the AI call returns, then calls `reset_sources()`. The FastAPI layer ships them as `SourceLink` objects (`app.py:43`) and `frontend/script.js` renders the `text` as a clickable anchor when `link` is set. Two consequences:

- Don't forget the reset — the next query will leak stale sources otherwise.
- If you add another source-producing tool, give it a `last_sources` attribute too; `ToolManager.get_last_sources` walks every registered tool and returns the first non-empty one (so only one tool's sources surface per query — last writer doesn't win, first finder does).

### Document ingestion

`backend/document_processor.py` expects a strict header format:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<body...>
```

- Lessons are split on `^Lesson\s+(\d+):` markers; an immediately following `Lesson Link:` line is consumed.
- Chunking is sentence-based (regex tuned to skip abbreviations), packed up to `CHUNK_SIZE=800` chars with `CHUNK_OVERLAP=100`.
- **Inconsistent context prefixing**: mid-document lessons prepend `"Lesson N content: "` only to the first chunk (line 184-188), but the final lesson prepends `"Course <title> Lesson N content: "` to *every* chunk (line 234). Embeddings differ accordingly — be aware when changing prefix logic.

### Ingestion dedup is title-only

`RAGSystem.add_course_folder` (`rag_system.py:75-100`) skips files whose parsed title already exists in the catalog. Editing a file's body without changing its title is silently ignored. To force a rebuild: delete `backend/chroma_db/` and restart, or call `add_course_folder(..., clear_existing=True)`.

### Sessions

`SessionManager` is **in-memory only** — restarts wipe history. Session IDs are assigned server-side on first request (`session_<n>` from a counter); the client echoes the issued ID back on subsequent calls. `MAX_HISTORY=2` exchanges are kept and formatted into the system prompt. `POST /api/session/clear` with a `session_id` drops that session's history (used by the frontend's "New chat" button).

### Frontend

Static files served by the same FastAPI app (`app.py:119`), so `/api` is same-origin. `frontend/script.js` renders assistant messages through `marked.parse()` **without sanitization** — the backend is trusted.

### Config knobs

All tunables live in `backend/config.py`:

- `ANTHROPIC_MODEL = "claude-sonnet-4-6"`
- `EMBEDDING_MODEL = "all-MiniLM-L6-v2"`
- `CHUNK_SIZE = 800`, `CHUNK_OVERLAP = 100`
- `MAX_RESULTS = 5` (top-k for content search)
- `MAX_HISTORY = 2` (exchanges, not messages)
- `CHROMA_PATH = "./chroma_db"` (relative to launch dir → `backend/chroma_db/`)
