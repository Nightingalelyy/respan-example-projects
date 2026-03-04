import os

from dotenv import load_dotenv

load_dotenv(override=True)

from pydantic_ai import Agent
from respan_tracing import RespanTelemetry
from respan_exporter_pydantic_ai import instrument_pydantic_ai

def main():
    # 1. Initialize Respan Telemetry
    # Ensure RESPAN_API_KEY is set in your environment
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-example",
        api_key=os.environ.get("RESPAN_API_KEY")
    )
    
    # 2. Instrument Pydantic AI
    # By default, it instruments globally. We pass kwargs as per BE conventions
    instrument_pydantic_ai(
        include_content=True,
        include_binary_content=True
    )
    
    # 3. Create an agent and run it
    # Pydantic AI Agent setup
    agent = Agent(
        model="openai:gpt-4o",
        system_prompt="You are a helpful assistant."
    )
    
    # Run the agent synchronously
    result = agent.run_sync("What is the capital of France?")
    
    print("Agent Output:", result.data)

if __name__ == "__main__":
    main()
