#!/usr/bin/env python3
"""
Multi-Turn Session — Multiple queries sharing a conversation session.

Demonstrates running sequential queries where the agent maintains context
across turns. Each turn is traced with its session ID.

Run:
    python sessions/multi_turn_test.py
"""

from dotenv import load_dotenv

load_dotenv(override=True)

import asyncio
import os

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage

from respan_exporter_anthropic_agents import RespanAnthropicAgentsExporter

API_KEY = os.getenv("RESPAN_API_KEY")
BASE_URL = os.getenv("RESPAN_BASE_URL")

exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


@pytest.mark.asyncio
async def test_multi_turn():
    """Run multiple turns and verify session tracking."""

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=1,
    )

    prompts = [
        "My name is Alice and I'm a software engineer.",
        "What is my name? Reply in one sentence.",
    ]

    for i, prompt in enumerate(prompts, 1):
        result = None
        async for message in exporter.query(prompt=prompt, options=options):
            if isinstance(message, ResultMessage):
                result = message

        if result:
            print(f"Turn {i}: subtype={result.subtype}")

        session_id = exporter._last_session_id
        print(f"  Session: {session_id}")

    print("\nView traces at: https://platform.respan.ai/platform/traces")
    print("Each turn appears as a separate trace with its session ID.")


if __name__ == "__main__":
    asyncio.run(test_multi_turn())
