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
from respan_tracing import RespanTelemetry, get_client
from respan_tracing.decorators import task
from respan_exporter_pydantic_ai import instrument_pydantic_ai

agent = Agent("openai:gpt-4o")

@task(name="customer_query")
def customer_query(query: str):
    # Set respan_params on the current span
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
    # 1. Initialize Respan Telemetry
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-params",
        api_key=respan_api_key,
        base_url=respan_base_url,
    )

    # 2. Instrument Pydantic AI
    instrument_pydantic_ai()

    # 3. Run the task
    output = customer_query("Hello, who are you?")
    print("Output:", output)

    telemetry.flush()

if __name__ == "__main__":
    main()
