"""
Wrapped Query — the simplest integration pattern.

Uses exporter.query() which handles hooks + tracking automatically.
One line to instrument, zero boilerplate.

Setup:
    pip install claude-agent-sdk respan-exporter-anthropic-agents python-dotenv

Run:
    python basic/wrapped_query_test.py

    # or with pytest:
    pytest basic/wrapped_query_test.py -v
"""

from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import os

import pytest
from claude_agent_sdk import ClaudeAgentOptions

from respan_exporter_anthropic_agents import RespanAnthropicAgentsExporter

API_KEY = os.getenv("RESPAN_API_KEY") or os.getenv("RESPAN_API_KEY")
BASE_URL = os.getenv("RESPAN_BASE_URL") or os.getenv("RESPAN_BASE_URL")

exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


@pytest.mark.asyncio
async def test_wrapped_query():
    """Use exporter.query() for automatic tracing — simplest pattern."""

    message_types = []

    async for message in exporter.query(
        prompt="Name three primary colors. One word each, comma separated.",
        options=ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            max_turns=1,
        ),
    ):
        msg_type = type(message).__name__
        message_types.append(msg_type)
        print(f"  {msg_type}")

    print(f"\nMessage flow: {' -> '.join(message_types)}")
    print("All traces exported automatically via exporter.query()")


if __name__ == "__main__":
    asyncio.run(test_wrapped_query())
