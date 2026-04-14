#!/usr/bin/env python3
"""
DSPy + OpenInference example for Respan tracing.

Uses openinference-instrumentation-dspy to auto-instrument DSPy
and exports spans to Respan via the respan-instrumentation-openinference wrapper.
"""
import os
from pathlib import Path

import dspy
from dotenv import load_dotenv
from openinference.instrumentation.dspy import DSPyInstrumentor
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

telemetry = RespanTelemetry(
    app_name="dspy-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

dspy_openinference = OpenInferenceInstrumentor(DSPyInstrumentor)
dspy_openinference.activate()

lm = dspy.LM(
    "openai/gpt-4o-mini",
    api_key=RESPAN_API_KEY,
    api_base=RESPAN_BASE_URL,
    temperature=0,
)
dspy.configure(lm=lm)


class HaikuWriter(dspy.Signature):
    """Write a haiku about the given topic. Output only the haiku."""

    topic: str = dspy.InputField()
    haiku: str = dspy.OutputField(desc="A three-line haiku poem")


@workflow(name="dspy_openinference_workflow")
def dspy_openinference_workflow(topic: str) -> str:
    cot = dspy.ChainOfThought(HaikuWriter)
    result = cot(topic=topic)
    return result.haiku


def main() -> None:
    print("=" * 60)
    print("DSPy OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = dspy_openinference_workflow(
            topic="recursion in programming"
        )
        print(result)
    finally:
        telemetry.flush()
        dspy_openinference.deactivate()


if __name__ == "__main__":
    main()
