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

### Tests / lint

There is no test suite, linter, or formatter configured in this repo. Don't invent commands for them.

## Architecture

This is a **tool-using RAG** chatbot: rather than always prepending retrieved chunks to the prompt, Claude is given a single search tool and decides whether to call it. The system prompt caps usage at one search per query.

### Request lifecycle

A `POST /api/query` results in **one or two Claude API calls**:

1. `app.py:query_documents` → `RAGSystem.query()` (`backend/rag_system.py:102`)
2. `AIGenerator.generate_response()` makes Claude call #1 with `tools=[search_course_content]` and `tool_choice=auto`.
3. If `stop_reason == "tool_use"`, `_handle_tool_execution` runs the tool and makes Claude call #2 **without tools** (prevents recursion). Otherwise the first response is returned directly.
4. The tool dispatches to `CourseSearchTool.execute()` → `VectorStore.search()`.

### Two ChromaDB collections

`VectorStore` (`backend/vector_store.py`) maintains two collections backed by `all-MiniLM-L6-v2` embeddings, persisted at `backend/chroma_db/`:

- **`course_catalog`** — one row per course (title is the primary ID). Used for **fuzzy course-name resolution**: when the tool gets `course_name="MCP"`, it does a 1-result vector query here to find the canonical title before filtering content.
- **`course_content`** — one row per chunk, with `course_title` / `lesson_number` / `chunk_index` metadata. The actual retrieval target.

### Sources side channel

`CourseSearchTool` stashes the source list of its last search on `self.last_sources`. `RAGSystem.query()` reads it via `ToolManager.get_last_sources()` **after** the AI call returns, then calls `reset_sources()`. This is how sources reach the UI without being part of the LLM's text response — don't forget the reset, or the next query leaks stale sources.

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

`SessionManager` is **in-memory only** — restarts wipe history. Session IDs are assigned server-side on first request (`session_<n>` from a counter); the client echoes the issued ID back on subsequent calls. `MAX_HISTORY=2` exchanges are kept and formatted into the system prompt.

### Frontend

Static files served by the same FastAPI app (`app.py:119`), so `/api` is same-origin. `frontend/script.js` renders assistant messages through `marked.parse()` **without sanitization** — the backend is trusted.

### Config knobs

All tunables live in `backend/config.py`:

- `ANTHROPIC_MODEL = "claude-sonnet-4-20250514"`
- `EMBEDDING_MODEL = "all-MiniLM-L6-v2"`
- `CHUNK_SIZE = 800`, `CHUNK_OVERLAP = 100`
- `MAX_RESULTS = 5` (top-k for content search)
- `MAX_HISTORY = 2` (exchanges, not messages)
- `CHROMA_PATH = "./chroma_db"` (relative to launch dir → `backend/chroma_db/`)
