import os
import sys

from dotenv import load_dotenv
from openinference.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry import trace

from crewai import Agent, Crew, Task
from respan_exporter_crewai.instrumentor import RespanCrewAIInstrumentor
from respan_exporter_crewai.utils import normalize_respan_base_url_for_gateway

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))

def main() -> None:
    """
    Respan Params: Passing customer_identifier, metadata, and custom tags.
    
    This script shows how to inject business-level properties like customer ID
    or specific environment details so that traces are easily searchable in Respan.
    """
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        print("Please set RESPAN_API_KEY environment variable.")
        sys.exit(1)

    base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
    os.environ["OPENAI_BASE_URL"] = normalize_respan_base_url_for_gateway(base_url)
    os.environ["OPENAI_API_KEY"] = api_key

    os.environ["RESPAN_CUSTOMER_IDENTIFIER"] = "cust_12345"
    os.environ["RESPAN_CUSTOMER_IDENTIFIER"] = "cust_12345"
    os.environ["RESPAN_ENVIRONMENT"] = "staging"

    # 1. Initialize general RespanTelemetry to set up the default TracerProvider
    from respan_tracing import RespanTelemetry, workflow, task, get_client
    # Apply tags globally to RespanTelemetry tracer via environment variables
    # (respan_tracing picks these up or uses RespanTelemetry)
    RespanTelemetry(api_key=api_key)

    RespanCrewAIInstrumentor().instrument(
        api_key=api_key,
        customer_identifier="cust_12345",
        environment="staging"
    )
    # CrewAI spans are emitted by OpenInference instrumentation.
    CrewAIInstrumentor().instrument()

    # 3. Get standard tracer to attach runtime metadata
    tracer = trace.get_tracer(__name__)

    # 4. Define Crew
    customer_agent = Agent(
        role="Customer Support",
        goal="Answer customer inquiries nicely.",
        backstory="You are a helpful customer service representative.",
    )

    support_task = Task(
        description="Help the user reset their password.",
        expected_output="A short password reset guide.",
        agent=customer_agent
    )

    crew = Crew(agents=[customer_agent], tasks=[support_task])

    @workflow(name="customer_inquiry")
    def run_crew():
        # Get the respan_tracing client to explicitly inject metadata and respan params
        client = get_client()
        if client:
            client.update_current_span(
                respan_params={
                    "customer_identifier": "cust_12345",
                    "customer_email": "demo_user@respan.ai",
                    "customer_name": "Demo User",
                    "session_identifier": "session_abc",
                    "metadata": {
                        "ticket_id": "TICKET-999",
                        "priority": "high",
                    }
                }
            )
        return crew.kickoff()

    # 5. Kickoff the crew inside a span to add extra custom metadata
    print("Running Crew with custom metadata...")
    result = run_crew()

    # Get the raw LLM calls to join the trace via headers
    # (By default OpenInference sets traceparent headers but we can force attributes)
    
    # Force flush so spans are exported before process exits.
    trace.get_tracer_provider().force_flush()
        
    print("\nResult:")
    print(result)

if __name__ == "__main__":
    main()
