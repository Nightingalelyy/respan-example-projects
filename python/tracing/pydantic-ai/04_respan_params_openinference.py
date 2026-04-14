#!/usr/bin/env python3
"""Setting customer_identifier, metadata, and custom_tags with OpenInference."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry, get_client
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
    return Agent(OPENAI_MODEL, instrument=INSTRUMENTATION_SETTINGS)


@task(name="customer_query")
def customer_query(query: str) -> str:
    client = get_client()
    if client:
        client.update_current_span(
            respan_params={
                "customer_identifier": "user_12345",
                "metadata": {
                    "plan": "premium",
                    "session_id": "abc-987",
                },
                "custom_tags": ["pydantic-ai", "openinference"],
            }
        )
    result = build_agent().run_sync(query)
    return result.output


@workflow(name="pydantic_ai_respan_params_openinference")
def run_customer_query(query: str) -> str:
    return customer_query(query)


def main() -> None:
    global INSTRUMENTATION_SETTINGS

    print("=" * 60)
    print("Pydantic AI OpenInference Respan Params")
    print("=" * 60)

    if not HAS_RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    telemetry = RespanTelemetry(
        app_name="pydantic-ai-openinference-params",
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
        output = run_customer_query("Hello, who are you?")
        print("Output:", output)
    finally:
        telemetry.flush()
        pydantic_ai_openinference.deactivate()


if __name__ == "__main__":
    main()
