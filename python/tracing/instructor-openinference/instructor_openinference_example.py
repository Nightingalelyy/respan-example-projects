#!/usr/bin/env python3
"""
Instructor + OpenInference example for Respan tracing.

Uses openinference-instrumentation-instructor to auto-instrument Instructor
and exports spans to Respan via the respan-instrumentation-openinference wrapper.

Instructor patches OpenAI's client to return structured Pydantic model outputs.
"""
import os
from pathlib import Path

import instructor
import openai
from dotenv import load_dotenv
from openinference.instrumentation.instructor import InstructorInstrumentor
from pydantic import BaseModel, Field
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
    app_name="instructor-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

instructor_oi = OpenInferenceInstrumentor(InstructorInstrumentor)
instructor_oi.activate()


class Haiku(BaseModel):
    line1: str = Field(description="First line of the haiku (5 syllables)")
    line2: str = Field(description="Second line of the haiku (7 syllables)")
    line3: str = Field(description="Third line of the haiku (5 syllables)")


client = instructor.from_openai(
    openai.OpenAI(api_key=RESPAN_API_KEY, base_url=RESPAN_BASE_URL)
)


@workflow(name="instructor_openinference_workflow")
def instructor_workflow(topic: str) -> Haiku:
    return client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=Haiku,
        messages=[
            {"role": "user", "content": f"Write a haiku about {topic}."},
        ],
        temperature=0,
        max_tokens=256,
    )


def main() -> None:
    print("=" * 60)
    print("Instructor OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        haiku = instructor_workflow(topic="recursion in programming")
        print(haiku.line1)
        print(haiku.line2)
        print(haiku.line3)
    finally:
        telemetry.flush()
        instructor_oi.deactivate()


if __name__ == "__main__":
    main()
