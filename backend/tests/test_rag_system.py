"""Tests for RAGSystem.query on content-related questions.

We patch AIGenerator.generate_response so no Anthropic call is made, but we
keep the real ToolManager / CourseSearchTool / VectorStore (over a temp
ChromaDB path) so the source-tracking + reset logic is exercised end-to-end.
"""
from unittest.mock import patch

import pytest

from models import Course, CourseChunk, Lesson
from rag_system import RAGSystem


class _CfgStub:
    """Minimal config shaped like backend.config.Config."""

    ANTHROPIC_API_KEY = "test-key"
    ANTHROPIC_MODEL = "claude-test"
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100
    MAX_RESULTS = 5
    MAX_HISTORY = 2

    def __init__(self, chroma_path: str):
        self.CHROMA_PATH = chroma_path


@pytest.fixture
def rag(tmp_path):
    cfg = _CfgStub(chroma_path=str(tmp_path / "chroma"))
    system = RAGSystem(cfg)

    course = Course(
        title="Test Course",
        course_link="http://course",
        instructor="Alice",
        lessons=[
            Lesson(lesson_number=1, title="Intro", lesson_link="http://l1"),
            Lesson(lesson_number=2, title="Deep dive", lesson_link="http://l2"),
        ],
    )
    chunks = [
        CourseChunk(
            content="Intro content about widgets.",
            course_title="Test Course",
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="Deep content about gizmos.",
            course_title="Test Course",
            lesson_number=2,
            chunk_index=1,
        ),
    ]
    system.vector_store.add_course_metadata(course)
    system.vector_store.add_course_content(chunks)
    return system


def test_query_passes_tool_definitions_and_manager_to_generator(rag):
    with patch.object(
        rag.ai_generator, "generate_response", return_value="answer"
    ) as gen:
        rag.query("anything")

    kwargs = gen.call_args.kwargs
    tool_names = [t["name"] for t in kwargs["tools"]]
    assert "search_course_content" in tool_names
    assert "get_course_outline" in tool_names
    assert kwargs["tool_manager"] is rag.tool_manager


def test_query_returns_sources_collected_by_search_tool(rag):
    def fake_generate(**kwargs):
        # Simulate Claude invoking the search tool.
        kwargs["tool_manager"].execute_tool(
            "search_course_content", query="widgets"
        )
        return "answer"

    with patch.object(rag.ai_generator, "generate_response", side_effect=fake_generate):
        answer, sources = rag.query("tell me about widgets")

    assert answer == "answer"
    assert sources, "expected sources from CourseSearchTool.last_sources"
    assert any(s["text"].startswith("Test Course") for s in sources)


def test_query_resets_sources_after_call(rag):
    def fake_generate(**kwargs):
        kwargs["tool_manager"].execute_tool(
            "search_course_content", query="widgets"
        )
        return "answer"

    with patch.object(rag.ai_generator, "generate_response", side_effect=fake_generate):
        rag.query("first")

    assert rag.search_tool.last_sources == []


def test_query_updates_session_history_when_session_id_supplied(rag):
    with patch.object(rag.ai_generator, "generate_response", return_value="A1"):
        sid = rag.session_manager.create_session()
        rag.query("What is X?", session_id=sid)

    history = rag.session_manager.get_conversation_history(sid)
    assert "What is X?" in history
    assert "A1" in history


def test_content_question_smoke_end_to_end(rag):
    """Full content-query choreography with the real search tool."""

    def fake_generate(**kwargs):
        kwargs["tool_manager"].execute_tool(
            "search_course_content", query="gizmos"
        )
        return "Gizmos are covered in lesson 2."

    with patch.object(rag.ai_generator, "generate_response", side_effect=fake_generate):
        answer, sources = rag.query("Tell me about gizmos")

    assert "Gizmos" in answer
    assert sources
    assert all("text" in s and "link" in s for s in sources)
