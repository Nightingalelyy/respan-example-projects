"""Tracing a Pydantic AI agent that uses tools.

This example is written so the agent is required to use a tool (add) to answer,
ensuring the exported trace contains tool-call spans.
"""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Route LLM calls through Respan (gateway pattern)
respan_api_key = os.environ["RESPAN_API_KEY"]
respan_base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
os.environ["OPENAI_BASE_URL"] = respan_base_url
os.environ["OPENAI_API_KEY"] = respan_api_key

from pydantic_ai import Agent
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow
from respan_exporter_pydantic_ai import instrument_pydantic_ai

agent = Agent(
    "openai:gpt-4o",
    system_prompt=(
        "You are a calculator assistant. You must use the provided tools for any arithmetic. "
        "Never compute numbers yourself; always call the add tool when asked to add numbers."
    ),
)

@agent.tool_plain
def add(a: int, b: int) -> int:
    """Add two numbers together."""
    return a + b


@workflow(name="calculator_agent_run")
def run_calculator_agent(prompt: str):
    result = agent.run_sync(prompt)
    return result.output


def main():
    # 1. Initialize Respan Telemetry
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-tool-use",
        api_key=respan_api_key,
        base_url=respan_base_url,
    )

    # 2. Instrument Pydantic AI
    instrument_pydantic_ai()

    # 3. Run the agent with a prompt that requires a tool call (so the trace contains tool-call spans)
    output = run_calculator_agent(
        "Use your add tool to compute 15 + 27, then reply with the result."
    )
    print("Agent Output:", output)

    telemetry.flush()


if __name__ == "__main__":
    main()
