import os
import sys

from dotenv import load_dotenv
from openinference.instrumentation.crewai import CrewAIInstrumentor
from crewai import Agent, Crew, Task
from respan_exporter_crewai.instrumentor import RespanCrewAIInstrumentor
from respan_exporter_crewai.utils import normalize_respan_base_url_for_gateway

# Assumes respan_sdk provides these decorators for unified tracing
from respan_tracing import RespanTelemetry, task, workflow

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))

def main() -> None:
    """
    Tracing: Combining generic @workflow / @task spans with CrewAI instrumentation.
    
    This example demonstrates how you can wrap a larger operation using RespanTelemetry
    and Respan decorators, whilst CrewAI's internals are implicitly traced and nested.
    """
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        print("Please set RESPAN_API_KEY environment variable.")
        sys.exit(1)

    base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
    os.environ["OPENAI_BASE_URL"] = normalize_respan_base_url_for_gateway(base_url)
    os.environ["OPENAI_API_KEY"] = api_key

    # 1. Initialize general RespanTelemetry (for @workflow / @task)
    telemetry = RespanTelemetry(api_key=api_key)

    # 2. Initialize CrewAI specific instrumentor
    RespanCrewAIInstrumentor().instrument(api_key=api_key)
    CrewAIInstrumentor().instrument()

    @task(name="setup_crew")
    def setup_crew() -> Crew:
        agent = Agent(
            role="Data Analyst",
            goal="Analyze the input data",
            backstory="You love looking at numbers and facts.",
        )
        data_task = Task(
            description="Analyze the number 42 and provide a fun fact.",
            expected_output="A fun fact about the number 42.",
            agent=agent
        )
        return Crew(agents=[agent], tasks=[data_task])

    @workflow(name="analyze_workflow")
    def run_analysis_workflow() -> str:
        crew = setup_crew()
        print("Running the analysis workflow...")
        return str(crew.kickoff())

    # 3. Execute the traced workflow
    result = run_analysis_workflow()
    print("\nWorkflow Result:")
    print(result)

if __name__ == "__main__":
    main()
