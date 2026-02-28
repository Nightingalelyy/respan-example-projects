"""
Hello World — Anthropic Agent SDK + Respan tracing.

The simplest possible example: ask Claude a question, see the trace in Respan.

Setup:
    pip install claude-agent-sdk respan-exporter-anthropic-agents python-dotenv

Run:
    python basic/hello_world_test.py

    # or with pytest:
    pytest basic/hello_world_test.py -v
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

# Create exporter — sends traces to Respan
exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


@pytest.mark.asyncio
async def test_hello_world():
    """Ask Claude a simple question and export the trace."""

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=1,
    )

    result_message = None

    # exporter.query() wraps the SDK query — handles hooks, prompt
    # tracking, and message export automatically.
    async for message in exporter.query(prompt="What is 2 + 2? Reply in one word.", options=options):
        if isinstance(message, ResultMessage):
            result_message = message

    print(f"\nResult: {result_message.subtype if result_message else 'none'}")
    print(f"Session: {exporter._last_session_id}")
    print(f"\nView trace at: https://platform.respan.ai/traces")


if __name__ == "__main__":
    asyncio.run(test_hello_world())
