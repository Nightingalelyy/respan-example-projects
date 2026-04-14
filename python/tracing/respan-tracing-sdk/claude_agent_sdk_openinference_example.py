#!/usr/bin/env python3
"""
Minimal Claude Agent SDK + OpenInference example for Respan tracing.

Tested end to end in a clean environment with:
    pip install claude-agent-sdk respan-ai respan-instrumentation-openinference openinference-instrumentation-claude-agent-sdk opentelemetry-semantic-conventions-ai python-dotenv
"""
import asyncio
import os
from pathlib import Path

import claude_agent_sdk
from claude_agent_sdk.types import ClaudeAgentOptions
from dotenv import load_dotenv
from openinference.instrumentation.claude_agent_sdk import ClaudeAgentSDKInstrumentor
from respan import Respan
from respan_instrumentation_openinference import OpenInferenceInstrumentor

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_AGENT_MODEL = os.getenv("CLAUDE_AGENT_MODEL", "sonnet")
HAS_RESPAN_API_KEY = bool(RESPAN_API_KEY)

respan = Respan(
    api_key=RESPAN_API_KEY,
    app_name="claude-agent-sdk-openinference-example",
    instrumentations=[OpenInferenceInstrumentor(ClaudeAgentSDKInstrumentor)],
)


def _extract_text(message: object) -> str:
    text_parts = []
    for block in getattr(message, "content", []) or []:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text:
            text_parts.append(text)
    return "\n".join(text_parts)


async def _run() -> None:
    print("=" * 60)
    print("Claude Agent SDK OpenInference Example")
    print("=" * 60)

    if not HAS_RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    options = ClaudeAgentOptions(
        model=CLAUDE_AGENT_MODEL,
        max_turns=1,
        env={"ANTHROPIC_API_KEY": ANTHROPIC_API_KEY} if ANTHROPIC_API_KEY else {},
    )

    assistant_text = ""
    final_result = ""

    try:
        async for message in claude_agent_sdk.query(
            prompt="Explain OpenInference tracing in one short sentence.",
            options=options,
        ):
            message_kind = message.__class__.__name__
            if message_kind == "AssistantMessage":
                assistant_text = _extract_text(message)
            elif message_kind == "ResultMessage":
                final_result = getattr(message, "result", "") or ""

        print(final_result or assistant_text or "[No text result returned]")
    except Exception as exc:
        print(f"Run failed: {exc}")
        print("Hint: set ANTHROPIC_API_KEY in .env, or run `claude auth login`.")
    finally:
        respan.flush()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
