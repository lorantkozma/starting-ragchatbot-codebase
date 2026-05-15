"""Tests that AIGenerator drives Claude's tool-use loop correctly.

The real Anthropic client is patched so no network call happens. We verify
that AIGenerator builds the right request params, dispatches tool_use blocks
to the tool_manager, and re-prompts Claude without tools to produce the final
answer.
"""
from unittest.mock import MagicMock, patch

import pytest

from ai_generator import AIGenerator

from .conftest import (
    make_anthropic_response,
    make_text_block,
    make_tool_use_block,
)


@pytest.fixture
def mock_anthropic_client():
    with patch("ai_generator.anthropic.Anthropic") as anthropic_cls:
        client = MagicMock()
        anthropic_cls.return_value = client
        yield client


def test_generate_response_returns_text_when_no_tool_use(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = make_anthropic_response(
        stop_reason="end_turn", content_blocks=[make_text_block("hi")]
    )

    gen = AIGenerator(api_key="k", model="claude-test")
    out = gen.generate_response(query="hello")

    assert out == "hi"
    assert mock_anthropic_client.messages.create.call_count == 1


def test_generate_response_triggers_tool_execution_when_stop_reason_is_tool_use(
    mock_anthropic_client,
):
    first = make_anthropic_response(
        stop_reason="tool_use",
        content_blocks=[
            make_tool_use_block(
                "search_course_content", {"query": "X"}, block_id="tu_1"
            )
        ],
    )
    second = make_anthropic_response(
        stop_reason="end_turn", content_blocks=[make_text_block("final answer")]
    )
    mock_anthropic_client.messages.create.side_effect = [first, second]

    tool_manager = MagicMock()
    tool_manager.execute_tool.return_value = "[MCP - Lesson 0]\nbody"

    gen = AIGenerator(api_key="k", model="claude-test")
    out = gen.generate_response(
        query="hello",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert out == "final answer"
    tool_manager.execute_tool.assert_called_once_with(
        "search_course_content", query="X"
    )
    assert mock_anthropic_client.messages.create.call_count == 2

    second_params = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    # Round 2 still carries tools — only the forced-final call drops them.
    assert second_params["tools"] == [{"name": "search_course_content"}]
    assert second_params["tool_choice"] == {"type": "auto"}
    last_message = second_params["messages"][-1]
    assert last_message["role"] == "user"
    assert last_message["content"][0]["type"] == "tool_result"
    assert last_message["content"][0]["tool_use_id"] == "tu_1"
    assert last_message["content"][0]["content"] == "[MCP - Lesson 0]\nbody"


def test_generate_response_includes_history_in_system_prompt(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = make_anthropic_response(
        stop_reason="end_turn", content_blocks=[make_text_block("ok")]
    )

    gen = AIGenerator(api_key="k", model="claude-test")
    gen.generate_response(query="q", conversation_history="prev")

    params = mock_anthropic_client.messages.create.call_args.kwargs
    assert "Previous conversation:\nprev" in params["system"]


def test_generate_response_passes_tools_and_auto_choice_when_tools_given(
    mock_anthropic_client,
):
    mock_anthropic_client.messages.create.return_value = make_anthropic_response(
        stop_reason="end_turn", content_blocks=[make_text_block("ok")]
    )
    gen = AIGenerator(api_key="k", model="claude-test")
    tools = [{"name": "search_course_content"}]
    gen.generate_response(query="q", tools=tools, tool_manager=MagicMock())

    params = mock_anthropic_client.messages.create.call_args.kwargs
    assert params["tools"] == tools
    assert params["tool_choice"] == {"type": "auto"}


def test_generate_response_omits_tools_when_none_given(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = make_anthropic_response(
        stop_reason="end_turn", content_blocks=[make_text_block("ok")]
    )
    gen = AIGenerator(api_key="k", model="claude-test")
    gen.generate_response(query="q")

    params = mock_anthropic_client.messages.create.call_args.kwargs
    assert "tools" not in params
    assert "tool_choice" not in params


def test_tool_execution_handles_multiple_tool_use_blocks(mock_anthropic_client):
    first = make_anthropic_response(
        stop_reason="tool_use",
        content_blocks=[
            make_tool_use_block("search_course_content", {"query": "X"}, "tu_1"),
            make_tool_use_block("get_course_outline", {"course_title": "MCP"}, "tu_2"),
        ],
    )
    second = make_anthropic_response(
        stop_reason="end_turn", content_blocks=[make_text_block("combined")]
    )
    mock_anthropic_client.messages.create.side_effect = [first, second]

    tool_manager = MagicMock()
    tool_manager.execute_tool.side_effect = ["search-out", "outline-out"]

    gen = AIGenerator(api_key="k", model="claude-test")
    out = gen.generate_response(
        query="q",
        tools=[{"name": "search_course_content"}, {"name": "get_course_outline"}],
        tool_manager=tool_manager,
    )

    assert out == "combined"
    assert tool_manager.execute_tool.call_count == 2

    second_params = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    tool_results = second_params["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in tool_results] == ["tu_1", "tu_2"]
    assert [r["content"] for r in tool_results] == ["search-out", "outline-out"]


# --- Sequential tool calling (MAX_TOOL_ROUNDS=2) ---------------------------


def test_two_rounds_of_tool_use_force_a_no_tools_final_call(mock_anthropic_client):
    """Round 1 tool_use → round 2 tool_use → forced final no-tools call."""
    r1 = make_anthropic_response(
        stop_reason="tool_use",
        content_blocks=[
            make_tool_use_block("get_course_outline", {"course_title": "X"}, "tu_1")
        ],
    )
    r2 = make_anthropic_response(
        stop_reason="tool_use",
        content_blocks=[
            make_tool_use_block(
                "search_course_content", {"query": "topic from lesson 4"}, "tu_2"
            )
        ],
    )
    r3 = make_anthropic_response(
        stop_reason="end_turn",
        content_blocks=[make_text_block("synthesized answer")],
    )
    mock_anthropic_client.messages.create.side_effect = [r1, r2, r3]

    tool_manager = MagicMock()
    tool_manager.execute_tool.side_effect = [
        "outline of X",
        "matching course content",
    ]

    gen = AIGenerator(api_key="k", model="claude-test")
    out = gen.generate_response(
        query="multi-step query",
        tools=[
            {"name": "get_course_outline"},
            {"name": "search_course_content"},
        ],
        tool_manager=tool_manager,
    )

    assert out == "synthesized answer"
    assert mock_anthropic_client.messages.create.call_count == 3
    assert tool_manager.execute_tool.call_count == 2
    third_params = mock_anthropic_client.messages.create.call_args_list[2].kwargs
    assert "tools" not in third_params
    assert "tool_choice" not in third_params


def test_first_round_text_only_makes_no_tool_dispatch(mock_anthropic_client):
    """If round 1 returns text directly, no tools execute and no extra call."""
    mock_anthropic_client.messages.create.return_value = make_anthropic_response(
        stop_reason="end_turn",
        content_blocks=[make_text_block("direct answer")],
    )
    tool_manager = MagicMock()

    gen = AIGenerator(api_key="k", model="claude-test")
    out = gen.generate_response(
        query="hello",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert out == "direct answer"
    assert mock_anthropic_client.messages.create.call_count == 1
    tool_manager.execute_tool.assert_not_called()


def test_tool_exception_terminates_loop_and_forces_final_no_tools_call(
    mock_anthropic_client,
):
    """A raised tool execution short-circuits to a forced final no-tools call."""
    r1 = make_anthropic_response(
        stop_reason="tool_use",
        content_blocks=[
            make_tool_use_block("search_course_content", {"query": "X"}, "tu_1")
        ],
    )
    r_final = make_anthropic_response(
        stop_reason="end_turn",
        content_blocks=[make_text_block("apology answer")],
    )
    mock_anthropic_client.messages.create.side_effect = [r1, r_final]

    tool_manager = MagicMock()
    tool_manager.execute_tool.side_effect = RuntimeError("boom")

    gen = AIGenerator(api_key="k", model="claude-test")
    out = gen.generate_response(
        query="trigger error",
        tools=[{"name": "search_course_content"}],
        tool_manager=tool_manager,
    )

    assert out == "apology answer"
    assert mock_anthropic_client.messages.create.call_count == 2
    final_params = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    assert "tools" not in final_params
    error_result = final_params["messages"][-1]["content"][0]
    assert error_result["type"] == "tool_result"
    assert error_result["tool_use_id"] == "tu_1"
    assert error_result["is_error"] is True
    assert "boom" in error_result["content"]


def test_message_history_preserved_across_three_calls(mock_anthropic_client):
    """The forced-final call sees the full transcript of both rounds."""
    r1 = make_anthropic_response(
        stop_reason="tool_use",
        content_blocks=[
            make_tool_use_block("get_course_outline", {"course_title": "X"}, "tu_1")
        ],
    )
    r2 = make_anthropic_response(
        stop_reason="tool_use",
        content_blocks=[
            make_tool_use_block("search_course_content", {"query": "Y"}, "tu_2")
        ],
    )
    r3 = make_anthropic_response(
        stop_reason="end_turn",
        content_blocks=[make_text_block("done")],
    )
    mock_anthropic_client.messages.create.side_effect = [r1, r2, r3]

    tool_manager = MagicMock()
    tool_manager.execute_tool.side_effect = ["outline-X", "content-Y"]

    gen = AIGenerator(api_key="k", model="claude-test")
    gen.generate_response(
        query="multi-step",
        tools=[
            {"name": "get_course_outline"},
            {"name": "search_course_content"},
        ],
        tool_manager=tool_manager,
    )

    third_messages = mock_anthropic_client.messages.create.call_args_list[2].kwargs[
        "messages"
    ]
    assert len(third_messages) == 5
    assert third_messages[0] == {"role": "user", "content": "multi-step"}
    assert third_messages[1]["role"] == "assistant"
    assert third_messages[1]["content"] == r1.content
    assert third_messages[2]["role"] == "user"
    assert third_messages[2]["content"][0]["tool_use_id"] == "tu_1"
    assert third_messages[2]["content"][0]["content"] == "outline-X"
    assert third_messages[3]["role"] == "assistant"
    assert third_messages[3]["content"] == r2.content
    assert third_messages[4]["role"] == "user"
    assert third_messages[4]["content"][0]["tool_use_id"] == "tu_2"
    assert third_messages[4]["content"][0]["content"] == "content-Y"


def test_extract_text_handles_response_whose_first_block_is_tool_use(
    mock_anthropic_client,
):
    """Single-call path must not IndexError when content[0] is tool_use."""
    mock_anthropic_client.messages.create.return_value = make_anthropic_response(
        stop_reason="end_turn",
        content_blocks=[
            make_tool_use_block("search_course_content", {"query": "X"}, "tu_1"),
            make_text_block("here is the answer"),
        ],
    )

    gen = AIGenerator(api_key="k", model="claude-test")
    # tool_manager omitted on purpose — exercises the non-loop path.
    out = gen.generate_response(query="q")

    assert out == "here is the answer"
