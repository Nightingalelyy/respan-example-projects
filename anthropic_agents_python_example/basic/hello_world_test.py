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
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query

from respan_exporter_anthropic_agents import RespanAnthropicAgentsExporter
from respan_exporter_anthropic_agents.utils import (
    extract_session_id_from_system_message,
)

API_KEY = os.getenv("RESPAN_API_KEY") or os.getenv("KEYWORDSAI_API_KEY")
BASE_URL = os.getenv("RESPAN_BASE_URL") or os.getenv("KEYWORDSAI_BASE_URL")

# Create exporter — sends traces to Respan
exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


@pytest.mark.asyncio
async def test_hello_world():
    """Ask Claude a simple question and export the trace."""

    # Attach exporter hooks to SDK options
    options = exporter.with_options(
        options=ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            max_turns=1,
        )
    )

    session_id = None
    result_message = None

    async for message in query(prompt="What is 2 + 2? Reply in one word.", options=options):
        # Track session ID
        if isinstance(message, SystemMessage):
            session_id = extract_session_id_from_system_message(
                system_message=message
            )
        if isinstance(message, ResultMessage):
            session_id = message.session_id
            result_message = message

        # Export each message to Respan
        await exporter.track_message(message=message, session_id=session_id)

    print(f"\nResult: {result_message.subtype if result_message else 'none'}")
    print(f"Session: {session_id}")
    print(f"\nView trace at: https://platform.keywordsai.co/traces")


if __name__ == "__main__":
    asyncio.run(test_hello_world())
