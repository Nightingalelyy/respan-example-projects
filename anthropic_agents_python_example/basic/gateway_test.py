"""
Gateway Integration — route through Respan, no Anthropic key needed.

The Respan gateway proxies Claude API calls, so you only need a single
Respan API key for both the LLM call and trace export.

Setup:
    pip install claude-agent-sdk respan-exporter-anthropic-agents python-dotenv

Environment:
    RESPAN_API_KEY=your_key    # only key needed

Run:
    python basic/gateway_test.py

    # or with pytest:
    pytest basic/gateway_test.py -v
"""

from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import os
import sys

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query

from respan_exporter_anthropic_agents import RespanAnthropicAgentsExporter
from respan_exporter_anthropic_agents.utils import (
    extract_session_id_from_system_message,
)

API_KEY = os.getenv("RESPAN_API_KEY") or os.getenv("KEYWORDSAI_API_KEY")
BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or os.getenv("KEYWORDSAI_BASE_URL")
    or "https://api.keywordsai.co/api"
).rstrip("/")

exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


@pytest.mark.asyncio
async def test_gateway_query():
    """Send a query through the Respan gateway and export traces."""

    if not API_KEY:
        pytest.skip("Set RESPAN_API_KEY to run this test")

    print(f"Gateway: {BASE_URL}")
    print(f"API key: {API_KEY[:8]}...\n")

    # Route Claude SDK through the Respan gateway — same key for auth + tracing
    options = exporter.with_options(
        options=ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            max_turns=1,
            env={
                "ANTHROPIC_BASE_URL": BASE_URL,
                "ANTHROPIC_AUTH_TOKEN": API_KEY,
                "ANTHROPIC_API_KEY": API_KEY,
            },
        )
    )

    session_id = None
    result = None

    async for message in query(
        prompt="Reply with exactly: gateway_ok",
        options=options,
    ):
        if isinstance(message, SystemMessage):
            session_id = extract_session_id_from_system_message(
                system_message=message
            )
        if isinstance(message, ResultMessage):
            session_id = message.session_id
            result = message

        await exporter.track_message(message=message, session_id=session_id)
        print(f"  {type(message).__name__}")

    if result:
        print(f"\nResult: subtype={result.subtype}, turns={result.num_turns}")
        if result.usage:
            print(f"Usage: {result.usage}")

    print(f"\nSession: {session_id}")
    print(f"View trace at: https://platform.keywordsai.co/traces")


if __name__ == "__main__":
    if not API_KEY:
        print("ERROR: Set RESPAN_API_KEY (or KEYWORDSAI_API_KEY)")
        sys.exit(1)
    asyncio.run(test_gateway_query())
