#!/usr/bin/env python3
"""Route LLM calls through Respan gateway with OpenInference content capture options."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openinference.instrumentation.pydantic_ai import OpenInferenceSpanProcessor
from pydantic_ai import Agent
from pydantic_ai.models.instrumented import InstrumentationSettings
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

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

if RESPAN_API_KEY:
    os.environ["OPENAI_BASE_URL"] = RESPAN_BASE_URL
    os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY


@workflow(name="pydantic_ai_openinference_gateway")
def run_agent() -> str:
    agent = Agent(
        model=OPENAI_MODEL,
        system_prompt="You are a helpful assistant.",
        instrument=InstrumentationSettings(
            include_content=True,
            include_binary_content=True,
            version=2,
        ),
    )
    result = agent.run_sync("What is the capital of France?")
    return result.output


def main() -> None:
    print("=" * 60)
    print("Pydantic AI OpenInference Gateway")
    print("=" * 60)

    if not HAS_RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    telemetry = RespanTelemetry(
        app_name="pydantic-ai-openinference-gateway",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        is_batching_enabled=False,
        instruments=set(),
    )
    pydantic_ai_openinference = OpenInferenceInstrumentor(OpenInferenceSpanProcessor)
    pydantic_ai_openinference.activate()

    try:
        print("Agent Output:", run_agent())
    finally:
        telemetry.flush()
        pydantic_ai_openinference.deactivate()


if __name__ == "__main__":
    main()
