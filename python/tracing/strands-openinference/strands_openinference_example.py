#!/usr/bin/env python3
"""
Strands Agents + OpenInference example for Respan tracing.

Uses openinference-instrumentation-strands-agents (a SpanProcessor that
transforms Strands' native OTel spans to OpenInference format) and exports
them to Respan via the respan-instrumentation-openinference wrapper.

NOTE: Strands uses a SpanProcessor-based instrumentor (not a standard
.instrument() instrumentor), so we must manually ensure the processor
ordering is:  Strands OI processor → OI→Traceloop translator → Respan exporter.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from openinference.instrumentation.strands_agents import (
    StrandsAgentsToOpenInferenceProcessor,
)
from opentelemetry import trace
from respan_instrumentation_openinference._translator import OpenInferenceTranslator
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow
from strands import Agent, tool
from strands.models.openai import OpenAIModel

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")

telemetry = RespanTelemetry(
    app_name="strands-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

# Manually set processor ordering so Strands processor runs FIRST.
# Strands OI processor mutates spans in-place, so it must run before
# the translator (OI→Traceloop) and the Respan exporter.
tp = trace.get_tracer_provider()
asp = getattr(tp, "_active_span_processor", None)
existing_processors = getattr(asp, "_span_processors", ())
asp._span_processors = (
    StrandsAgentsToOpenInferenceProcessor(),
    OpenInferenceTranslator(),
    *existing_processors,
)


@tool
def get_weather(city: str) -> dict:
    """Get the current weather for a city.

    Args:
        city: The name of the city.
    """
    weather_data = {
        "tokyo": {"temp": "22°C", "condition": "Sunny"},
        "london": {"temp": "15°C", "condition": "Cloudy"},
        "new york": {"temp": "18°C", "condition": "Partly cloudy"},
    }
    data = weather_data.get(city.lower(), {"temp": "20°C", "condition": "Unknown"})
    return {
        "status": "success",
        "content": [{"text": f"The weather in {city} is {data['condition']} at {data['temp']}."}],
    }


model = OpenAIModel(
    client_args={
        "api_key": RESPAN_API_KEY,
        "base_url": RESPAN_BASE_URL,
    },
    model_id="gpt-4o-mini",
    params={"max_tokens": 512, "temperature": 0},
)


@workflow(name="strands_openinference_workflow")
def strands_openinference_workflow(prompt: str) -> str:
    agent = Agent(
        model=model,
        tools=[get_weather],
        system_prompt="You are a helpful weather assistant. Use the get_weather tool when asked about weather. Give a brief, friendly response.",
    )
    result = agent(prompt)
    return str(result)


def main() -> None:
    print("=" * 60)
    print("Strands Agents OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = strands_openinference_workflow(
            prompt="What's the weather like in Tokyo?"
        )
        print(result)
    finally:
        telemetry.flush()


if __name__ == "__main__":
    main()
