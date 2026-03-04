#!/usr/bin/env python3
"""
Basic Gateway — Route Claude Agent SDK calls through Respan gateway.

Only needs RESPAN_API_KEY — no Anthropic key required. The gateway proxies
Claude API calls, so a single key handles both the LLM call and trace export.

Setup:
    pip install claude-agent-sdk respan-exporter-anthropic-agents python-dotenv

Run:
    python basic_gateway.py
"""

import asyncio
import os
import sys
from typing import Optional

from dotenv import load_dotenv
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage
from respan_exporter_anthropic_agents import RespanAnthropicAgentsExporter

load_dotenv(override=True)

API_KEY = os.getenv("RESPAN_API_KEY")
BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api").rstrip("/")

exporter = RespanAnthropicAgentsExporter(
    api_key=API_KEY,
    base_url=BASE_URL,
)


async def main():
    if not API_KEY:
        print("ERROR: Set RESPAN_API_KEY")
        sys.exit(1)

    # The Anthropic SDK appends /v1/messages to ANTHROPIC_BASE_URL,
    # so point it at the gateway's /anthropic passthrough path.
    # Final URL: {BASE_URL}/anthropic/v1/messages
    gateway_url = f"{BASE_URL}/anthropic"

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=1,
        env={
            "ANTHROPIC_BASE_URL": gateway_url,
            "ANTHROPIC_AUTH_TOKEN": API_KEY,
            "ANTHROPIC_API_KEY": API_KEY,
        },
    )

    result: Optional[ResultMessage] = None
    async for message in exporter.query(
        prompt="Reply with exactly: gateway_ok",
        options=options,
    ):
        msg_type = type(message).__name__
        print(f"  {msg_type}")
        if isinstance(message, ResultMessage):
            result = message

    if result:
        print(f"\nResult: subtype={result.subtype}, turns={result.num_turns}")
        print(f"Session: {exporter._last_session_id}")
        print("View trace at: https://platform.respan.ai/platform/traces")


if __name__ == "__main__":
    asyncio.run(main())
