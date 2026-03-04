#!/usr/bin/env python3
"""
Tool Use via Gateway — Run agent with tools, routed through Respan gateway.

Demonstrates tool calls (Read, Glob, Grep) going through the gateway
with a single RESPAN_API_KEY for both LLM and tracing.

Run:
    python tool_use_gateway.py
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

    gateway_url = f"{BASE_URL}/anthropic"

    options = ClaudeAgentOptions(
        permission_mode="bypassPermissions",
        max_turns=3,
        allowed_tools=["Read", "Glob", "Grep"],
        env={
            "ANTHROPIC_BASE_URL": gateway_url,
            "ANTHROPIC_AUTH_TOKEN": API_KEY,
            "ANTHROPIC_API_KEY": API_KEY,
        },
    )

    result: Optional[ResultMessage] = None
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
        print("Check Respan traces to see tool spans (Read, Glob, etc.)")


if __name__ == "__main__":
    asyncio.run(main())
