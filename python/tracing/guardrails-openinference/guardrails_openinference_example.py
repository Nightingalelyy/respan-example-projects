#!/usr/bin/env python3
"""
Guardrails AI + OpenInference example for Respan tracing.

Uses openinference-instrumentation-guardrails to auto-instrument Guardrails AI
and exports spans to Respan via the respan-instrumentation-openinference wrapper.

NOTE: The instrumentation only supports guardrails-ai >=0.4.5,<0.5.1.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")

os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY or ""
os.environ["OPENAI_BASE_URL"] = RESPAN_BASE_URL
os.environ["OPENAI_API_BASE"] = RESPAN_BASE_URL

from openinference.instrumentation.guardrails import GuardrailsInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="guardrails-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

guardrails_oi = OpenInferenceInstrumentor(GuardrailsInstrumentor)
guardrails_oi.activate()

import openai
import guardrails as gd

guard = gd.Guard.from_string(
    validators=[],
    description="A guard that validates haiku output",
)


@workflow(name="guardrails_openinference_workflow")
def guardrails_workflow() -> str:
    result = guard(
        llm_api=openai.chat.completions.create,
        msg_history=[
            {"role": "user", "content": "Write a short haiku about recursion in programming. Output ONLY the haiku."},
        ],
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=256,
    )
    return result.validated_output or ""


def main() -> None:
    print("=" * 60)
    print("Guardrails AI OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = guardrails_workflow()
        print(result)
    finally:
        telemetry.flush()
        guardrails_oi.deactivate()


if __name__ == "__main__":
    main()
