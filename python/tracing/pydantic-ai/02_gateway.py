"""Route LLM calls through Respan gateway with content capture options."""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Route LLM calls through Respan (gateway pattern — only RESPAN_API_KEY needed)
respan_api_key = os.environ["RESPAN_API_KEY"]
respan_base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
os.environ["OPENAI_BASE_URL"] = respan_base_url
os.environ["OPENAI_API_KEY"] = respan_api_key

from pydantic_ai import Agent
from respan import Respan
from respan_instrumentation_pydantic_ai import PydanticAIInstrumentor


def main():
    # 1. Initialize Respan with PydanticAI instrumentation plugin
    respan = Respan(
        app_name="pydantic-ai-gateway",
        api_key=respan_api_key,
        base_url=respan_base_url,
        instrumentations=[
            PydanticAIInstrumentor(
                include_content=True,
                include_binary_content=True,
            ),
        ],
    )

    # 2. Create an agent and run it
    agent = Agent(
        model="openai:gpt-4o",
        system_prompt="You are a helpful assistant.",
    )
    result = agent.run_sync("What is the capital of France?")
    print("Agent Output:", result.output)

    respan.flush()


if __name__ == "__main__":
    main()
