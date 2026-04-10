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
from respan import Respan, workflow
from respan_instrumentation_pydantic_ai import PydanticAIInstrumentor

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
    # 1. Initialize Respan with PydanticAI instrumentation plugin
    respan = Respan(
        app_name="pydantic-ai-tool-use",
        api_key=respan_api_key,
        base_url=respan_base_url,
        instrumentations=[
            PydanticAIInstrumentor(
                include_content=True,
                include_binary_content=True,
            ),
        ],
    )

    # 2. Run the agent with a prompt that requires a tool call
    output = run_calculator_agent(
        "Use your add tool to compute 15 + 27, then reply with the result."
    )
    print("Agent Output:", output)

    respan.flush()


if __name__ == "__main__":
    main()
