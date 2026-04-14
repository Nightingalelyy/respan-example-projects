#!/usr/bin/env python3
"""Workflow/task spans with OpenInference + Pydantic AI."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import task, workflow

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")
OPENAI_MODEL = os.getenv("PYDANTIC_AI_OPENAI_MODEL", "openai:gpt-4o")
HAS_RESPAN_API_KEY = bool(RESPAN_API_KEY)
INSTRUMENTATION_SETTINGS: InstrumentationSettings | None = None

if RESPAN_API_KEY:
    os.environ["OPENAI_BASE_URL"] = RESPAN_BASE_URL
    os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY


def build_agent() -> Agent:
    if INSTRUMENTATION_SETTINGS is None:
        raise RuntimeError("Instrumentation settings must be initialized before building the agent.")
    return Agent(
        OPENAI_MODEL,
        system_prompt="You are a helpful travel assistant.",
        instrument=INSTRUMENTATION_SETTINGS,
    )


@task(name="fetch_destination_info")
def fetch_destination_info(destination: str) -> str:
    result = build_agent().run_sync(f"Give me a one-sentence summary of {destination}.")
    return result.output


@workflow(name="pydantic_ai_travel_planning_openinference")
def travel_planning_workflow(destination: str) -> str:
    return fetch_destination_info(destination)


def main() -> None:
    global INSTRUMENTATION_SETTINGS

    print("=" * 60)
    print("Pydantic AI OpenInference Tracing")
    print("=" * 60)

    if not HAS_RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    telemetry = RespanTelemetry(
        app_name="pydantic-ai-openinference-tracing",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        is_batching_enabled=False,
        instruments=set(),
    )
    pydantic_ai_openinference = OpenInferenceInstrumentor(OpenInferenceSpanProcessor)
    pydantic_ai_openinference.activate()

    try:
        INSTRUMENTATION_SETTINGS = InstrumentationSettings(
            tracer_provider=telemetry.tracer.tracer_provider,
            version=2,
        )
        output = travel_planning_workflow("Paris")
        print("Workflow Output:", output)
    finally:
        telemetry.flush()
        pydantic_ai_openinference.deactivate()


if __name__ == "__main__":
    main()
