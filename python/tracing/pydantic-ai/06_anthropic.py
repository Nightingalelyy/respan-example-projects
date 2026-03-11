"""Anthropic (Claude) via Respan gateway — proves token extraction works without OAI instrumentation."""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Route Anthropic calls through Respan gateway
respan_api_key = os.environ["RESPAN_API_KEY"]
respan_base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
os.environ["ANTHROPIC_BASE_URL"] = respan_base_url
os.environ["ANTHROPIC_API_KEY"] = respan_api_key

from pydantic_ai import Agent
from respan_tracing import RespanTelemetry, Instruments
from respan_exporter_pydantic_ai import instrument_pydantic_ai


def main():
    # 1. Initialize Respan Telemetry
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-anthropic",
        api_key=respan_api_key,
        base_url=respan_base_url,
        block_instruments={Instruments.REQUESTS, Instruments.URLLIB3, Instruments.HTTPX},
    )

    # 2. Instrument Pydantic AI
    instrument_pydantic_ai()

    # 3. Create an Anthropic agent and run it
    agent = Agent(
        model="anthropic:claude-sonnet-4-20250514",
        system_prompt="You are a helpful assistant. Keep answers brief.",
    )
    result = agent.run_sync("What is the largest ocean on Earth?")
    print("Agent Output:", result.output)

    telemetry.flush()


if __name__ == "__main__":
    main()
