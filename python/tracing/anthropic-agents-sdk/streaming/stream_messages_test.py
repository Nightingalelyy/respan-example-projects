#!/usr/bin/env python3
"""
Stream Messages — Process each message type as it arrives.

Shows how to handle the different message types streamed by the SDK:
SystemMessage, UserMessage, AssistantMessage, ResultMessage, StreamEvent.

Run:
    python streaming/stream_messages_test.py
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
async def test_stream_messages():
    """Stream messages and inspect each type."""

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=1,
    )

    message_flow = []

    async for message in exporter.query(
        prompt="Write a haiku about programming.",
        options=options,
    ):
        msg_type = type(message).__name__
        message_flow.append(msg_type)

        if msg_type == "SystemMessage":
            print(f"  [System] Session started")
        elif msg_type == "UserMessage":
            print(f"  [User] Prompt submitted")
        elif msg_type == "AssistantMessage":
            # Extract text content from assistant response
            text_parts = []
            for block in getattr(message, "content", []):
                if hasattr(block, "text"):
                    text_parts.append(block.text)
            if text_parts:
                print(f"  [Assistant] {' '.join(text_parts)[:100]}")
        elif isinstance(message, ResultMessage):
            print(f"  [Result] subtype={message.subtype}, turns={message.num_turns}")
        else:
            print(f"  [{msg_type}]")

    print(f"\nMessage flow: {' -> '.join(message_flow)}")
    print("All messages traced automatically via exporter.query()")


if __name__ == "__main__":
    asyncio.run(test_stream_messages())
