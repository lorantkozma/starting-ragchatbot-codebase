"""Shared fixtures and helpers for backend tests."""
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from vector_store import SearchResults, VectorStore


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


@pytest.fixture
def mock_vector_store() -> MagicMock:
    """A MagicMock that mimics the VectorStore interface used by tools."""
    store = MagicMock(spec=VectorStore)
    store.search.return_value = make_search_results()
    store.get_lesson_link.return_value = None
    store.get_course_link.return_value = None
    return store
