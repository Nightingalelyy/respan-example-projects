"""Workflow/task spans with @workflow and @task decorators."""

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
from respan_tracing.decorators import workflow, task
from respan_exporter_pydantic_ai import instrument_pydantic_ai

agent = Agent("openai:gpt-4o", system_prompt="You are a helpful travel assistant.")

@task(name="fetch_destination_info")
def fetch_destination_info(destination: str) -> str:
    result = agent.run_sync(f"Give me a one-sentence summary of {destination}.")
    return result.output

@workflow(name="travel_planning_workflow")
def travel_planning_workflow(destination: str):
    info = fetch_destination_info(destination)
    return info

def main():
    # 1. Initialize Respan Telemetry
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-tracing",
        api_key=respan_api_key,
        base_url=respan_base_url,
    )

    # 2. Instrument Pydantic AI
    instrument_pydantic_ai()

    # 3. Run the workflow
    output = travel_planning_workflow("Paris")
    print("Workflow Output:", output)

    telemetry.flush()

if __name__ == "__main__":
    main()
