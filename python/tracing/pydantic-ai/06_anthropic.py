"""Anthropic (Claude) via Respan gateway — proves token extraction works without OAI instrumentation."""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Route Anthropic calls through Respan gateway
respan_api_key = os.environ["RESPAN_API_KEY"]
respan_base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
# Anthropic SDK appends /v1/messages, so base URL must include /anthropic
os.environ["ANTHROPIC_BASE_URL"] = f"{respan_base_url}/anthropic"
os.environ["ANTHROPIC_API_KEY"] = respan_api_key

from pydantic_ai import Agent
from respan import Respan
from respan_instrumentation_pydantic_ai import PydanticAIInstrumentor


def main():
    # 1. Initialize Respan with PydanticAI instrumentation plugin
    respan = Respan(
        app_name="pydantic-ai-anthropic",
        api_key=respan_api_key,
        base_url=respan_base_url,
        instrumentations=[
            PydanticAIInstrumentor(
                include_content=True,
                include_binary_content=True,
            ),
        ],
    )

    # 2. Create an Anthropic agent and run it
    agent = Agent(
        model="anthropic:claude-sonnet-4-20250514",
        system_prompt="You are a helpful assistant. Keep answers brief.",
    )
    result = agent.run_sync("What is the largest ocean on Earth?")
    print("Agent Output:", result.output)

    respan.flush()


if __name__ == "__main__":
    main()
