"""
Tool Use — trace agent tool calls through Respan.

Runs a query that uses Claude Code's built-in tools (Read, Glob, Grep),
then exports the full trace including tool spans.

Setup:
    pip install claude-agent-sdk respan-exporter-anthropic-agents python-dotenv

Run:
    python basic/tool_use_test.py

    # or with pytest:
    pytest basic/tool_use_test.py -v
"""

from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import os

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from respan_exporter_anthropic_agents import RespanAnthropicAgentsExporter

API_KEY = os.getenv("RESPAN_API_KEY") or os.getenv("RESPAN_API_KEY")
BASE_URL = os.getenv("RESPAN_BASE_URL") or os.getenv("RESPAN_BASE_URL")

exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


@pytest.mark.asyncio
async def test_tool_use():
    """Run a query that uses tools and verify tool spans are exported."""

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=3,
        allowed_tools=["Read", "Glob", "Grep"],
    )

    result = None

    async for message in exporter.query(
        prompt="List the Python files in the current directory. Just show filenames.",
        options=options,
    ):
        msg_type = type(message).__name__
        print(f"  {msg_type}")
        if isinstance(message, ResultMessage):
            result = message

    if result:
        print(f"\nResult: subtype={result.subtype}, turns={result.num_turns}")

    print(f"\nSession: {exporter._last_session_id}")
    print("Check Respan traces to see tool spans (Read, Glob, etc.)")


if __name__ == "__main__":
    asyncio.run(test_tool_use())
