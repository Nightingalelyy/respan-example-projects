"""Bare-minimum sanity check: instrument + run one agent call."""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Route LLM calls through Respan (gateway pattern — only RESPAN_API_KEY needed)
respan_api_key = os.environ["RESPAN_API_KEY"]
respan_base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
os.environ["OPENAI_BASE_URL"] = respan_base_url
os.environ["OPENAI_API_KEY"] = respan_api_key

from pydantic_ai import Agent
from respan_tracing import RespanTelemetry
from respan_exporter_pydantic_ai import instrument_pydantic_ai

def main():
    # 1. Initialize Respan Telemetry
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-hello-world",
        api_key=respan_api_key,
        base_url=respan_base_url,
    )

    # 2. Instrument Pydantic AI
    instrument_pydantic_ai()

    # 3. Create an agent and run it
    agent = Agent(
        model="openai:gpt-4o",
        system_prompt="You are a helpful assistant.",
    )
    result = agent.run_sync("What is the capital of France?")
    print("Agent Output:", result.output)

    telemetry.flush()

if __name__ == "__main__":
    main()
