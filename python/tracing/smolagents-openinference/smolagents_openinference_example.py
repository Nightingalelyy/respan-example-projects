#!/usr/bin/env python3
"""
smolagents + OpenInference example for Respan tracing.

Uses openinference-instrumentation-smolagents to auto-instrument HuggingFace smolagents
and exports spans to Respan via the respan-instrumentation-openinference wrapper.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from openinference.instrumentation.smolagents import SmolagentsInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow
from smolagents import CodeAgent, OpenAIServerModel

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")

telemetry = RespanTelemetry(
    app_name="smolagents-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

smolagents_openinference = OpenInferenceInstrumentor(SmolagentsInstrumentor)
smolagents_openinference.activate()


@workflow(name="smolagents_openinference_workflow")
def smolagents_openinference_workflow(prompt: str) -> str:
    model = OpenAIServerModel(
        model_id="gpt-4o-mini",
        api_key=RESPAN_API_KEY,
        api_base=RESPAN_BASE_URL,
    )

    agent = CodeAgent(
        tools=[],
        model=model,
        max_steps=2,
        verbosity_level=1,
    )

    return agent.run(prompt)


def main() -> None:
    print("=" * 60)
    print("smolagents OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = smolagents_openinference_workflow(
            prompt="Write a haiku about recursion in programming. Just output the haiku, nothing else."
        )
        print(f"\nFinal result: {result}")
    finally:
        telemetry.flush()
        smolagents_openinference.deactivate()


if __name__ == "__main__":
    main()
