import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(), override=True)

# Route LLM calls through Respan (gateway pattern — only RESPAN_API_KEY needed)
respan_api_key = os.environ["RESPAN_API_KEY"]
os.environ["OPENAI_BASE_URL"] = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
os.environ["OPENAI_API_KEY"] = respan_api_key

from pydantic_ai import Agent
from respan_tracing import RespanTelemetry
from respan_exporter_pydantic_ai import instrument_pydantic_ai

def main():
    # 1. Initialize Respan Telemetry
    respan_base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
    telemetry = RespanTelemetry(
        app_name="pydantic-ai-hello-world",
        api_key=respan_api_key,
        base_url=respan_base_url
    )
    
    # 2. Instrument Pydantic AI
    instrument_pydantic_ai(
        include_content=True,
        include_binary_content=True
    )
    
    # 3. Create an agent and run it
    # Note: Requires OPENAI_API_KEY to be set in your environment
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
