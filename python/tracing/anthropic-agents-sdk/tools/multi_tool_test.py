#!/usr/bin/env python3
"""
Multi-Tool — Agent using multiple tools in sequence.

Demonstrates a multi-turn agent that uses several tools to accomplish
a task, with each tool call captured as a child span.

Run:
    python tools/multi_tool_test.py
"""

from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import os

import pytest
from claude_agent_sdk import ClaudeAgentOptions

from respan_exporter_anthropic_agents import RespanAnthropicAgentsExporter

API_KEY = os.getenv("RESPAN_API_KEY")
BASE_URL = os.getenv("RESPAN_BASE_URL")

exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


@pytest.mark.asyncio
async def test_multi_tool():
    """Run a query that requires multiple tool calls in sequence."""
    from _sdk_runtime import query_for_result

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=5,
        allowed_tools=["Read", "Glob", "Grep"],
    )

    tool_count = 0

    def _on_message(message):
        nonlocal tool_count
        msg_type = type(message).__name__
        print(f"  {msg_type}")
        # AssistantMessage with tool_use blocks indicates tool calls
        if hasattr(message, "content") and hasattr(message.content, "__iter__"):
            for block in getattr(message, "content", []):
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_count += 1

    result = await query_for_result(
        exporter=exporter,
        prompt=(
            "Find all Python files in the current directory, "
            "then read the first one and tell me what it does. Be concise."
        ),
        options=options,
        on_message=_on_message,
    )

    print(f"\nResult: subtype={result.subtype}, turns={result.num_turns}")
    print(f"Session: {exporter._last_session_id}")
    print("Check Respan traces to see the full tool call sequence.")


if __name__ == "__main__":
    asyncio.run(test_multi_tool())
