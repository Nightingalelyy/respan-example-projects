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
    Hello World: Bare minimum sanity check to verify Respan integration with CrewAI.
    
    This script initializes the Respan CrewAI instrumentor, creates a simple agent 
    and task, and runs the crew. The traces (workflow, tasks, agents, generations)
    will automatically be sent to Respan.
    """
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        print("Please set RESPAN_API_KEY environment variable.")
        sys.exit(1)

    base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
    os.environ["OPENAI_BASE_URL"] = normalize_respan_base_url_for_gateway(base_url)
    os.environ["OPENAI_API_KEY"] = api_key

    # 1. Initialize the instrumentor
    RespanCrewAIInstrumentor().instrument(api_key=api_key)
    CrewAIInstrumentor().instrument()

    # 2. Define standard CrewAI objects
    hello_agent = Agent(
        role="Greeter",
        goal="Provide a cheerful greeting",
        backstory="You are a helpful and polite assistant who loves saying hello.",
        verbose=True
    )

    hello_task = Task(
        description="Say hello to the user and give them a short welcome message.",
        expected_output="A single paragraph greeting.",
        agent=hello_agent
    )

    crew = Crew(
        agents=[hello_agent],
        tasks=[hello_task],
        verbose=True
    )

    # 3. Kickoff the crew
    print("Running CrewAI Hello World...")
    result = crew.kickoff()
    
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    main()
