#!/usr/bin/env python3
"""
Sequential multi-agent CrewAI example instrumented through OpenInference for Respan.
"""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from respan_tracing import RespanTelemetry, get_client
from respan_tracing.decorators import workflow

ROOT_ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

os.environ["CREWAI_TRACING_ENABLED"] = "false"
logging.getLogger("opentelemetry.trace").setLevel(logging.ERROR)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")
RESPAN_MODEL = os.getenv("RESPAN_MODEL", "gpt-4o-mini")

if RESPAN_API_KEY:
    os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY
    os.environ["OPENAI_API_BASE"] = RESPAN_BASE_URL
    os.environ["OPENAI_MODEL_NAME"] = RESPAN_MODEL

telemetry = RespanTelemetry(
    app_name="crewai-sequential-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

# CrewAI installs a global tracer provider at import time, so import it only
# after RespanTelemetry has registered the provider that OpenInference should use.
from crewai import Agent, Crew, LLM, Process, Task
from openinference.instrumentation.crewai import CrewAIInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor

crewai_openinference = OpenInferenceInstrumentor(CrewAIInstrumentor)
crewai_openinference.activate()


def build_gateway_llm() -> LLM:
    return LLM(
        model=RESPAN_MODEL,
        base_url=RESPAN_BASE_URL,
        api_key=RESPAN_API_KEY,
        temperature=0,
        max_tokens=180,
    )


def render_result(result: object) -> str:
    raw = getattr(result, "raw", None)
    if isinstance(raw, str) and raw:
        return raw
    return str(result)


def build_crew() -> Crew:
    researcher = Agent(
        role="Observability Researcher",
        goal="Produce compact notes about tracing and CrewAI",
        backstory="You extract only the most useful facts for developers.",
        llm=build_gateway_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )

    writer = Agent(
        role="Technical Writer",
        goal="Turn research notes into a tiny markdown summary",
        backstory="You write crisp summaries for developer docs.",
        llm=build_gateway_llm(),
        verbose=False,
        allow_delegation=False,
        max_iter=3,
    )

    research_task = Task(
        description=(
            "List three short facts about why OpenInference tracing is useful "
            "for CrewAI applications."
        ),
        expected_output="Three short facts in plain text.",
        agent=researcher,
    )

    writing_task = Task(
        description=(
            "Turn the research notes into three markdown bullet points and one "
            "final sentence telling developers why the Respan gateway is useful."
        ),
        expected_output=(
            "Three markdown bullet points followed by one short closing sentence."
        ),
        agent=writer,
        context=[research_task],
    )

    return Crew(
        agents=[researcher, writer],
        tasks=[research_task, writing_task],
        process=Process.sequential,
        verbose=False,
        tracing=False,
    )


@workflow(name="crewai_sequential_openinference_workflow")
def run_crewai_workflow() -> object:
    client = get_client()
    if client:
        client.update_current_span(
            respan_params={
                "customer_identifier": "crewai-sequential-openinference-example",
                "metadata": {
                    "example_name": "crewai_sequential_openinference_example",
                    "gateway_model": RESPAN_MODEL,
                },
            }
        )
    return build_crew().kickoff()


def main() -> None:
    print("=" * 60)
    print("CrewAI Sequential OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    try:
        result = run_crewai_workflow()
        print(render_result(result))
    finally:
        telemetry.flush()
        crewai_openinference.deactivate()


if __name__ == "__main__":
    main()
