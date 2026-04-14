#!/usr/bin/env python3
"""
Google ADK + OpenInference example for Respan tracing.

Uses openinference-instrumentation-google-adk to auto-instrument Google ADK
and exports spans to Respan via the respan-instrumentation-openinference wrapper.
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from google.adk.agents.llm_agent import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
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
    app_name="google-adk-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

adk_openinference = OpenInferenceInstrumentor(GoogleADKInstrumentor)
adk_openinference.activate()


def get_current_weather(city: str) -> dict:
    """Returns the current weather for a given city. This is a mock tool."""
    weather_data = {
        "tokyo": {"temp": "22°C", "condition": "Sunny"},
        "london": {"temp": "15°C", "condition": "Cloudy"},
        "new york": {"temp": "18°C", "condition": "Partly cloudy"},
    }
    data = weather_data.get(city.lower(), {"temp": "20°C", "condition": "Unknown"})
    return {"status": "success", "city": city, "temperature": data["temp"], "condition": data["condition"]}


agent = Agent(
    model=LiteLlm(
        model="openai/gpt-4o-mini",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
    ),
    name="weather_agent",
    description="An agent that reports weather for cities.",
    instruction="You are a helpful weather assistant. Use the get_current_weather tool when asked about weather. Give a brief, friendly response.",
    tools=[get_current_weather],
)


session_service = InMemorySessionService()


@workflow(name="google_adk_openinference_workflow")
async def google_adk_openinference_workflow(prompt: str) -> str:
    session = await session_service.create_session(
        app_name="weather_app",
        user_id="test_user",
    )

    runner = InMemoryRunner(agent, app_name="weather_app")
    runner.session_service = session_service

    input_content = Content(parts=[Part(text=prompt)])
    final_text = ""
    async for event in runner.run_async(
        new_message=input_content,
        user_id=session.user_id,
        session_id=session.id,
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(
                part.text for part in event.content.parts if getattr(part, "text", None)
            )

    return final_text


async def main() -> None:
    print("=" * 60)
    print("Google ADK OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = await google_adk_openinference_workflow(
            prompt="What's the weather like in Tokyo?"
        )
        print(result)
    finally:
        telemetry.flush()
        adk_openinference.deactivate()


if __name__ == "__main__":
    asyncio.run(main())
