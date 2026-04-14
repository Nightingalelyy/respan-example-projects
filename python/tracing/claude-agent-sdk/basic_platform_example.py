#!/usr/bin/env python3
"""
Most basic Claude Agent SDK example using local Respan instrumentation.

Run:
    python basic_platform_example.py
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

import claude_agent_sdk  # type: ignore[reportMissingImports]
from claude_agent_sdk import ClaudeAgentOptions, ResultMessage  # type: ignore[reportMissingImports]
from respan import Respan  # type: ignore[reportMissingImports]
from respan_instrumentation_claude_agent_sdk import (  # type: ignore[reportMissingImports]
    ClaudeAgentSDKInstrumentor,
)

EXAMPLE_REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_PATH = EXAMPLE_REPO_ROOT / ".env"
EXAMPLE_CWD = Path(__file__).resolve().parent

BASIC_PROMPT = 'Reply with exactly "hello_from_claude_agent_sdk_basic_example".'
CUSTOMER_IDENTIFIER = "claude-agent-sdk-basic-example"
EXAMPLE_NAME = "claude_agent_sdk_basic_platform_example"
APP_NAME = "claude-agent-sdk-basic-example"


def _load_example_env() -> Path | None:
    if ROOT_ENV_PATH.exists():
        load_dotenv(ROOT_ENV_PATH, override=True)
        return ROOT_ENV_PATH
    load_dotenv(override=True)
    return None


LOADED_ENV_PATH = _load_example_env()

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api").rstrip("/")
CLAUDE_AGENT_MODEL = os.getenv("CLAUDE_AGENT_MODEL", "sonnet")
ANTHROPIC_GATEWAY_URL = f"{RESPAN_BASE_URL}/anthropic"

if not RESPAN_API_KEY:
    raise RuntimeError(
        "RESPAN_GATEWAY_API_KEY or RESPAN_API_KEY must be set in the repo-root .env."
    )

os.environ.setdefault("ANTHROPIC_API_KEY", RESPAN_API_KEY)
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", RESPAN_API_KEY)
os.environ.setdefault("ANTHROPIC_BASE_URL", ANTHROPIC_GATEWAY_URL)


def _build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=CLAUDE_AGENT_MODEL,
        max_turns=1,
        permission_mode="bypassPermissions",
        cwd=str(EXAMPLE_CWD),
        env={
            "ANTHROPIC_API_KEY": RESPAN_API_KEY,
            "ANTHROPIC_AUTH_TOKEN": RESPAN_API_KEY,
            "ANTHROPIC_BASE_URL": ANTHROPIC_GATEWAY_URL,
        },
    )


async def _run_basic_query() -> str:
    result_text: str | None = None
    async for message in claude_agent_sdk.query(
        prompt=BASIC_PROMPT,
        options=_build_options(),
    ):
        if isinstance(message, ResultMessage):
            result_text = message.result or ""

    if result_text is None:
        raise RuntimeError("Claude Agent SDK query completed without a ResultMessage.")
    return result_text


def _print_summary(result_text: str) -> None:
    print("\n=== Claude Agent SDK Basic Example ===")
    print(f"Prompt:              {BASIC_PROMPT}")
    print(f"Claude result:       {result_text}")
    print(f"Base URL:            {RESPAN_BASE_URL}")
    print(f"Anthropic URL:       {ANTHROPIC_GATEWAY_URL}")
    print(f"Claude model:        {CLAUDE_AGENT_MODEL}")
    print(f"Loaded .env:         {LOADED_ENV_PATH or 'find_dotenv fallback'}")
    print()
    print("Check the trace on Respan platform with:")
    print(f"  customer_identifier = {CUSTOMER_IDENTIFIER}")
    print(f"  metadata.example_name = {EXAMPLE_NAME}")


async def main() -> None:
    respan = Respan(
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        app_name=APP_NAME,
        instrumentations=[
            ClaudeAgentSDKInstrumentor(
                agent_name=APP_NAME,
                capture_content=True,
            )
        ],
        metadata={
            "example_name": EXAMPLE_NAME,
            "sdk": "claude-agent-sdk",
            "example_type": "basic",
            "local_instrumentation": True,
        },
        environment=os.getenv("RESPAN_ENVIRONMENT"),
    )

    try:
        with respan.propagate_attributes(customer_identifier=CUSTOMER_IDENTIFIER):
            result_text = await _run_basic_query()
        _print_summary(result_text=result_text)
    finally:
        respan.flush()


if __name__ == "__main__":
    asyncio.run(main())
