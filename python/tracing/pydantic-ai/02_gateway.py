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
from respan_exporter_pydantic_ai import instrument_pydantic_ai

def main():
    # 1. Initialize Respan Telemetry
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-example",
        api_key=respan_api_key,
        base_url=respan_base_url
    )
    
    # 3. Instrument Pydantic AI
    # By default, it instruments globally. We pass kwargs as per BE conventions
    instrument_pydantic_ai(
        include_content=True,
        include_binary_content=True
    )
    
    # 4. Create an agent and run it
    # Pydantic AI Agent setup
    agent = Agent(
        model="openai:gpt-4o",
        system_prompt="You are a helpful assistant."
    )
    
    # Run the agent synchronously
    result = agent.run_sync("What is the capital of France?")
    
    print("Agent Output:", result.output)

    telemetry.flush()  # Ensure spans are exported before exit

if __name__ == "__main__":
    main()
