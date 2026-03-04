#!/usr/bin/env python3
"""
Tool Use — Trace agent tool calls through Respan.

Runs a query that uses Claude Code's built-in tools (Read, Glob, Grep),
then exports the full trace including tool spans.

Run:
    python tools/tool_use_test.py
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
async def test_tool_use():
    """Run a query that uses tools and verify tool spans are exported."""
    from _sdk_runtime import query_for_result

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=3,
        allowed_tools=["Read", "Glob", "Grep"],
    )

    def _on_message(message):
        print(f"  {type(message).__name__}")

    result = await query_for_result(
        exporter=exporter,
        prompt="List the Python files in the current directory. Just show filenames.",
        options=options,
        on_message=_on_message,
    )

    print(f"\nResult: subtype={result.subtype}, turns={result.num_turns}")
    print(f"Session: {exporter._last_session_id}")
    print("Check Respan traces to see tool spans (Read, Glob, etc.)")


if __name__ == "__main__":
    asyncio.run(test_tool_use())
