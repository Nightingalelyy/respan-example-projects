import os
import sys

from dotenv import load_dotenv
from openinference.instrumentation.crewai import CrewAIInstrumentor
from crewai import Agent, Crew, Task
from respan_exporter_crewai.instrumentor import RespanCrewAIInstrumentor
from respan_exporter_crewai.utils import normalize_respan_base_url_for_gateway

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))

def main() -> None:
    """
    Gateway: Route LLM calls through the Respan proxy.
    
    This allows you to log the raw LLM completions, leverage Respan fallbacks, 
    and avoid exposing your vendor API keys directly.
    """
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        print("Please set RESPAN_API_KEY environment variable.")
        sys.exit(1)

    base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")

    # 1. Setup OpenAI environment variables to use Respan Gateway
    os.environ["OPENAI_BASE_URL"] = normalize_respan_base_url_for_gateway(base_url)
    os.environ["OPENAI_API_KEY"] = api_key

    # 2. Instrument the CrewAI integration for tracing
    RespanCrewAIInstrumentor().instrument(
        api_key=api_key,
        base_url=base_url
    )
    CrewAIInstrumentor().instrument()

    # 3. Define agents and tasks
    history_agent = Agent(
        role="Historian",
        goal="Explain brief historical facts",
        backstory="An expert in world history.",
        verbose=True
    )

    history_task = Task(
        description="Explain the significance of the printing press in 2 sentences.",
        expected_output="A 2-sentence explanation.",
        agent=history_agent
    )

    crew = Crew(
        agents=[history_agent],
        tasks=[history_task],
        verbose=True
    )

    # 4. Kickoff the crew
    print("Running CrewAI via Respan Gateway...")
    result = crew.kickoff()
    
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    main()
