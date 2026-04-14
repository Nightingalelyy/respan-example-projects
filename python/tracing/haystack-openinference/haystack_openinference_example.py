#!/usr/bin/env python3
"""
Haystack + OpenInference example for Respan tracing.

Uses openinference-instrumentation-haystack to auto-instrument Haystack pipelines
and exports spans to Respan via the respan-instrumentation-openinference wrapper.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from haystack import Pipeline
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from haystack.utils import Secret
from openinference.instrumentation.haystack import HaystackInstrumentor
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
    app_name="haystack-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

haystack_oi = OpenInferenceInstrumentor(HaystackInstrumentor)
haystack_oi.activate()

pipe = Pipeline()
pipe.add_component(
    "llm",
    OpenAIChatGenerator(
        api_key=Secret.from_token(RESPAN_API_KEY),
        api_base_url=RESPAN_BASE_URL,
        model="gpt-4o-mini",
        generation_kwargs={"temperature": 0, "max_tokens": 256},
    ),
)


@workflow(name="haystack_openinference_workflow")
def haystack_workflow(topic: str) -> str:
    messages = [ChatMessage.from_user(f"Write a short haiku about {topic}. Output ONLY the haiku.")]
    result = pipe.run({"llm": {"messages": messages}})
    return result["llm"]["replies"][0].text


def main() -> None:
    print("=" * 60)
    print("Haystack OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = haystack_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        haystack_oi.deactivate()


if __name__ == "__main__":
    main()
