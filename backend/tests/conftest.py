"""Shared pytest fixtures for the backend test suite.

The fixtures here cover three concerns:

1. Anthropic response factories — build `Message`-shaped objects (with
   `content` blocks, `stop_reason`, `usage`) without hitting the API. Used by
   tests that exercise `AIGenerator` and its tool loop.
2. A `VectorStore` MagicMock with sane defaults. Most tests want a working
   store that returns empty results; override `search.return_value`,
   `get_existing_course_titles.return_value`, etc. per-test.
3. A FastAPI test app + `TestClient`. Because `backend/app.py` mounts
   `../frontend` at startup (and would also ingest `../docs`), importing it
   under pytest is unreliable — we build an equivalent app inline here from
   the same Pydantic models and route handlers, but wired to a mock
   `RAGSystem`.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from vector_store import SearchResults, VectorStore


# ---------------------------------------------------------------------------
# Module-level helpers (imported directly by tests)
# ---------------------------------------------------------------------------


def make_search_results(
    documents: Optional[List[str]] = None,
    metadata: Optional[List[Dict[str, Any]]] = None,
    distances: Optional[List[float]] = None,
    error: Optional[str] = None,
) -> SearchResults:
    """Build a SearchResults with sensible defaults for tests."""
    docs = documents if documents is not None else []
    metas = metadata if metadata is not None else []
    dists = distances if distances is not None else [0.0] * len(docs)
    return SearchResults(documents=docs, metadata=metas, distances=dists, error=error)


def make_text_block(text: str) -> SimpleNamespace:
    """Mimic an Anthropic content block of type 'text'."""
    return SimpleNamespace(type="text", text=text)


def make_tool_use_block(
    name: str, tool_input: Dict[str, Any], block_id: str = "tu_1"
) -> SimpleNamespace:
    """Mimic an Anthropic content block of type 'tool_use'."""
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=block_id)


def make_anthropic_response(
    stop_reason: str, content_blocks: List[SimpleNamespace]
) -> SimpleNamespace:
    """Mimic the response shape that ai_generator reads.

    Reads: .stop_reason, .content[i].type, .content[i].text, .content[i].name,
           .content[i].input, .content[i].id
    """
    return SimpleNamespace(stop_reason=stop_reason, content=content_blocks)


# ---------------------------------------------------------------------------
# Anthropic response fixtures (factory-style)
# ---------------------------------------------------------------------------


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(tool_id: str, name: str, input_: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=tool_id, name=name, input=input_)


@pytest.fixture
def text_block():
    """Factory: build a single text content block."""
    return _text_block


@pytest.fixture
def tool_use_block():
    """Factory: build a single tool_use content block."""
    return _tool_use_block


@pytest.fixture
def anthropic_message():
    """Factory for an Anthropic `Message`-shaped object.

    Pass a list of content blocks (see `text_block` / `tool_use_block`) and a
    `stop_reason`. Returns an object whose attribute access matches what the
    SDK exposes, which is all `AIGenerator` actually reads.
    """

    def _make(content: Iterable[Any], stop_reason: str = "end_turn") -> SimpleNamespace:
        return SimpleNamespace(
            content=list(content),
            stop_reason=stop_reason,
            usage=SimpleNamespace(input_tokens=0, output_tokens=0),
        )

    return _make


# ---------------------------------------------------------------------------
# VectorStore mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """A MagicMock that mimics the VectorStore interface used by tools."""
    store = MagicMock(spec=VectorStore)
    store.search.return_value = make_search_results()
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = None
    store.get_existing_course_titles.return_value = []
    store.get_course_count.return_value = 0
    return store


# ---------------------------------------------------------------------------
# Sample course data
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_course_titles() -> List[str]:
    return [
        "Building Toward Computer Use with Anthropic",
        "MCP: Build Rich-Context AI Apps with Anthropic",
        "Advanced Retrieval for AI with Chroma",
    ]


@pytest.fixture
def sample_query_answer() -> str:
    return "Computer use lets Claude operate a virtual machine via screenshots and tool calls."


@pytest.fixture
def sample_sources() -> List[str]:
    return [
        "Building Toward Computer Use with Anthropic - Lesson 2",
        "Building Toward Computer Use with Anthropic - Lesson 3",
    ]


# ---------------------------------------------------------------------------
# RAGSystem mock + FastAPI test app
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_rag_system(sample_query_answer, sample_sources, sample_course_titles):
    """A `RAGSystem`-shaped MagicMock with realistic defaults.

    `query` returns (answer, sources). `get_course_analytics` returns the
    canned title list. `session_manager.create_session` returns a fixed id so
    tests can assert on it.
    """
    rag = MagicMock()
    rag.query.return_value = (sample_query_answer, list(sample_sources))
    rag.get_course_analytics.return_value = {
        "total_courses": len(sample_course_titles),
        "course_titles": list(sample_course_titles),
    }
    rag.session_manager = MagicMock()
    rag.session_manager.create_session.return_value = "session_test_1"
    return rag


# API request/response models — defined at module scope so FastAPI's
# `get_type_hints` can resolve them when the route function is registered
# inside the fixture. Locally-scoped Pydantic models inside a closure end
# up being treated as query parameters, which is the bug FastAPI's
# inspection has when a type isn't resolvable from the function's module.
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    session_id: str


class CourseStats(BaseModel):
    total_courses: int
    course_titles: List[str]


@pytest.fixture
def test_app(mock_rag_system) -> FastAPI:
    """A FastAPI app that mirrors `backend/app.py` without static mounts.

    The production app mounts `../frontend` and ingests `../docs` on startup
    — both fail under pytest. This rebuilds the same routes against the
    `mock_rag_system` fixture so tests stay hermetic.
    """

    app = FastAPI(title="Course Materials RAG System (test)")

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest) -> QueryResponse:
        try:
            session_id = request.session_id or mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as exc:  # mirror app.py
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats() -> CourseStats:
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @app.get("/")
    async def root() -> dict:
        return {"status": "ok", "service": "Course Materials RAG System"}

    return app


@pytest.fixture
def client(test_app) -> TestClient:
    return TestClient(test_app)
