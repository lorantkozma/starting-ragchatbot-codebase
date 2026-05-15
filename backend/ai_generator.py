import anthropic
from typing import List, Optional, Dict, Any, Tuple

class AIGenerator:
    """Handles interactions with Anthropic's Claude API for generating responses"""

    # Cap on tool-enabled API rounds per user query. Each round = one Claude
    # call with tools + execution of any tool_use blocks it returns. After this
    # many rounds (or on tool failure) one forced no-tools call produces the
    # final text answer.
    MAX_TOOL_ROUNDS = 2

    # Static system prompt to avoid rebuilding on each call
    SYSTEM_PROMPT = """ You are an AI assistant specialized in course materials and educational content with access to tools for searching course information and retrieving course outlines.

Available Tools:
- `search_course_content`: Search course materials for specific content. Use for questions about lesson contents, concepts, or detailed educational material.
- `get_course_outline`: Retrieve a course outline — returns the course title, the course link, and the complete list of lessons (lesson number and lesson title for each). Use for outline / table-of-contents style questions, e.g. "what lessons are in course X", "show me the outline of Y".

Tool Usage:
- **Up to two sequential tool calls per query.** After you see the result of a tool call, you may make one more tool call to refine your answer — for example, look up a course outline first and then search a specific lesson, or compare information across two courses. Do not call tools more than twice. If two calls don't yield enough, answer with what you have.
- Do not repeat the same tool call with identical arguments — a second identical call will not return new information.
- Synthesize tool results into accurate, fact-based responses.
- If a tool yields no results, state this clearly without offering alternatives.

Response Protocol:
- **General knowledge questions**: Answer using existing knowledge without calling any tool
- **Course content questions**: Use `search_course_content` first, then answer
- **Course outline questions**: Use `get_course_outline` first, then answer. Your response **must** include the course title, the course link, and the number and title of every lesson returned by the tool.
- **Multi-step questions** (e.g. "find a course discussing the same topic as lesson 4 of course X"): use the first tool call to discover the intermediate fact, then a second tool call to act on it, then answer.
- **No meta-commentary**:
 - Provide direct answers only — no reasoning process, tool explanations, or question-type analysis
 - Do not mention "based on the search results" or similar phrasing


All responses must be:
1. **Brief, Concise and focused** - Get to the point quickly
2. **Educational** - Maintain instructional value
3. **Clear** - Use accessible language
4. **Example-supported** - Include relevant examples when they aid understanding
Provide only the direct answer to what was asked.
"""

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

        # Pre-build base API parameters
        self.base_params = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 800
        }

    def generate_response(self, query: str,
                         conversation_history: Optional[str] = None,
                         tools: Optional[List] = None,
                         tool_manager=None) -> str:
        """
        Generate AI response with optional sequential tool usage.

        When `tools` and `tool_manager` are both provided, Claude may invoke
        tools across up to `MAX_TOOL_ROUNDS` sequential rounds before a final
        no-tools call produces the answer. Otherwise this is a single call.
        """
        system_content = (
            f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
            if conversation_history
            else self.SYSTEM_PROMPT
        )

        messages: List[Dict[str, Any]] = [{"role": "user", "content": query}]

        if tools and tool_manager:
            return self._run_tool_loop(messages, system_content, tools, tool_manager)

        api_params = {
            **self.base_params,
            "messages": messages,
            "system": system_content,
        }
        if tools:
            api_params["tools"] = tools
            api_params["tool_choice"] = {"type": "auto"}

        response = self.client.messages.create(**api_params)
        return self._extract_text(response)

    def _run_tool_loop(
        self,
        messages: List[Dict[str, Any]],
        system_content: str,
        tools: List,
        tool_manager,
    ) -> str:
        """
        Sequential tool-use state machine.

        Three named exits:
          (a) round cap reached -> forced no-tools final call
          (b) Claude returns no tool_use blocks -> return its text now
          (c) tool execution raised -> forced no-tools final call so Claude
              can phrase the failure to the user
        """
        for round_idx in range(1, self.MAX_TOOL_ROUNDS + 1):
            response = self.client.messages.create(
                **self.base_params,
                messages=messages,
                system=system_content,
                tools=tools,
                tool_choice={"type": "auto"},
            )

            if response.stop_reason != "tool_use":
                # (b) Claude is done — no more tool calls.
                return self._extract_text(response)

            messages.append({"role": "assistant", "content": response.content})
            tool_result_blocks, had_error = self._dispatch_tool_calls(
                response.content, tool_manager
            )
            messages.append({"role": "user", "content": tool_result_blocks})

            if had_error:
                # (c) bail out; let Claude explain the failure without tools.
                return self._force_final_text(messages, system_content)

            if round_idx == self.MAX_TOOL_ROUNDS:
                # (a) used the round budget — force final text without tools.
                return self._force_final_text(messages, system_content)

        # Unreachable — the loop always returns via (a), (b), or (c).
        return self._force_final_text(messages, system_content)

    def _dispatch_tool_calls(
        self, response_content, tool_manager
    ) -> Tuple[List[Dict[str, Any]], bool]:
        """Execute every tool_use block in `response_content`.

        Returns (tool_result_blocks, had_error). An exception in any single
        tool execution is captured as an `is_error: True` tool_result and
        flips `had_error` so the caller can terminate the loop.
        """
        tool_result_blocks: List[Dict[str, Any]] = []
        had_error = False

        for block in response_content:
            if getattr(block, "type", None) != "tool_use":
                continue
            try:
                result = tool_manager.execute_tool(block.name, **block.input)
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
            except Exception as exc:  # noqa: BLE001 - intentional broad catch
                had_error = True
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": f"Tool execution failed: {exc!s}",
                    "is_error": True,
                })

        return tool_result_blocks, had_error

    def _force_final_text(
        self, messages: List[Dict[str, Any]], system_content: str
    ) -> str:
        """One final Claude call without tools to produce the answer text."""
        response = self.client.messages.create(
            **self.base_params,
            messages=messages,
            system=system_content,
        )
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response) -> str:
        """Return the first text block in `response.content`, or "" if none.

        Guards against responses whose first content block is `tool_use`
        (or where content is empty), which would IndexError on `content[0].text`.
        """
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""