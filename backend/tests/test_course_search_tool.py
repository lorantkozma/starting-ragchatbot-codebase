"""Tests for CourseSearchTool.execute and result formatting."""
from search_tools import CourseSearchTool

from .conftest import make_search_results


def test_execute_returns_formatted_results_when_documents_found(mock_vector_store):
    mock_vector_store.search.return_value = make_search_results(
        documents=["alpha body", "beta body"],
        metadata=[
            {"course_title": "MCP", "lesson_number": 1},
            {"course_title": "MCP", "lesson_number": 2},
        ],
    )
    mock_vector_store.get_lesson_link.side_effect = ["http://l1", "http://l2"]

    tool = CourseSearchTool(mock_vector_store)
    output = tool.execute(query="hello")

    assert "[MCP - Lesson 1]" in output
    assert "alpha body" in output
    assert "[MCP - Lesson 2]" in output
    assert "beta body" in output
    assert tool.last_sources == [
        {"text": "MCP - Lesson 1", "link": "http://l1"},
        {"text": "MCP - Lesson 2", "link": "http://l2"},
    ]


def test_execute_returns_no_content_message_when_empty(mock_vector_store):
    mock_vector_store.search.return_value = make_search_results()
    tool = CourseSearchTool(mock_vector_store)

    assert tool.execute(query="nothing") == "No relevant content found."


def test_execute_appends_course_filter_to_empty_message(mock_vector_store):
    mock_vector_store.search.return_value = make_search_results()
    tool = CourseSearchTool(mock_vector_store)

    output = tool.execute(query="nothing", course_name="MCP")

    assert "No relevant content found" in output
    assert "in course 'MCP'" in output


def test_execute_appends_lesson_filter_to_empty_message(mock_vector_store):
    mock_vector_store.search.return_value = make_search_results()
    tool = CourseSearchTool(mock_vector_store)

    output = tool.execute(query="nothing", lesson_number=2)

    assert "No relevant content found" in output
    assert "in lesson 2" in output


def test_execute_returns_error_passthrough(mock_vector_store):
    mock_vector_store.search.return_value = make_search_results(error="boom")
    tool = CourseSearchTool(mock_vector_store)

    assert tool.execute(query="anything") == "boom"


def test_execute_passes_args_to_vector_store_search(mock_vector_store):
    tool = CourseSearchTool(mock_vector_store)
    tool.execute(query="q", course_name="MCP", lesson_number=3)

    mock_vector_store.search.assert_called_once_with(
        query="q", course_name="MCP", lesson_number=3
    )


def test_execute_handles_lesson_num_none_without_calling_get_lesson_link(mock_vector_store):
    mock_vector_store.search.return_value = make_search_results(
        documents=["body"],
        metadata=[{"course_title": "MCP"}],  # no lesson_number
    )
    tool = CourseSearchTool(mock_vector_store)
    output = tool.execute(query="q")

    mock_vector_store.get_lesson_link.assert_not_called()
    assert tool.last_sources == [{"text": "MCP", "link": None}]
    assert "[MCP]" in output


def test_tool_definition_schema(mock_vector_store):
    tool = CourseSearchTool(mock_vector_store)
    schema = tool.get_tool_definition()

    assert schema["name"] == "search_course_content"
    props = schema["input_schema"]["properties"]
    assert "query" in props
    assert "course_name" in props
    assert "lesson_number" in props
    assert schema["input_schema"]["required"] == ["query"]
