"""Setting customer_identifier, metadata, and custom_tags on spans."""

import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Route LLM calls through Respan (gateway pattern)
respan_api_key = os.environ["RESPAN_API_KEY"]
respan_base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
os.environ["OPENAI_BASE_URL"] = respan_base_url
os.environ["OPENAI_API_KEY"] = respan_api_key

from pydantic_ai import Agent
from respan import Respan, get_client, task
from respan_instrumentation_pydantic_ai import PydanticAIInstrumentor

agent = Agent("openai:gpt-4o")


@task(name="customer_query")
def customer_query(query: str):
    client = get_client()
    if client:
        client.update_current_span(
            respan_params={
                "customer_identifier": "user_12345",
                "metadata": {
                    "plan": "premium",
                    "session_id": "abc-987",
                },
                "custom_tags": ["pydantic-ai", "test-run"],
            }
        )
    result = agent.run_sync(query)
    return result.output


def main():
    # 1. Initialize Respan with PydanticAI instrumentation plugin
    respan = Respan(
        app_name="pydantic-ai-params",
        api_key=respan_api_key,
        base_url=respan_base_url,
        instrumentations=[
            PydanticAIInstrumentor(
                include_content=True,
                include_binary_content=True,
            ),
        ],
    )

    # 2. Run the task
    output = customer_query("Hello, who are you?")
    print("Output:", output)

    respan.flush()


if __name__ == "__main__":
    main()
