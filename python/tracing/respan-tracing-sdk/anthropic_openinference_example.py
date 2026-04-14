#!/usr/bin/env python3
"""
Anthropic + OpenInference example for Respan tracing.

This example shows the new Anthropic tracing path:
1. Initialize `RespanTelemetry`
2. Activate `OpenInferenceInstrumentor(AnthropicInstrumentor)`
3. Create and use the Anthropic client normally
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic
from openinference.instrumentation.anthropic import AnthropicInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry, get_client
from respan_tracing.decorators import task, workflow
from respan_tracing.instruments import Instruments

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")
ANTHROPIC_GATEWAY_URL = f"{RESPAN_BASE_URL}/anthropic"
HAS_RESPAN_API_KEY = bool(RESPAN_API_KEY)
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")

telemetry = RespanTelemetry(
    app_name="anthropic-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    # Block Anthropic auto-discovery so this example uses the explicit
    # OpenInference wrapper path instead.
    block_instruments={Instruments.ANTHROPIC, Instruments.REQUESTS, Instruments.URLLIB3},
)

anthropic_openinference = OpenInferenceInstrumentor(AnthropicInstrumentor)
anthropic_openinference.activate()
anthropic_client = Anthropic(
    api_key=RESPAN_API_KEY or "test-key",
    base_url=ANTHROPIC_GATEWAY_URL,
)


@task(name="anthropic_completion")
def anthropic_completion(prompt: str) -> str:
    response = anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    if not response.content:
        return ""
    return response.content[0].text


@workflow(name="anthropic_openinference_workflow")
def anthropic_openinference_workflow(prompt: str) -> str:
    client = get_client()
    if client:
        client.update_current_span(
            respan_params={
                "customer_identifier": "anthropic-openinference-demo",
                "metadata": {"model": ANTHROPIC_MODEL},
            }
        )
    return anthropic_completion(prompt=prompt)


def main() -> None:
    print("=" * 60)
    print("Anthropic OpenInference Example")
    print("=" * 60)

    if not HAS_RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    try:
        result = anthropic_openinference_workflow(
            prompt="Explain OpenInference tracing for Anthropic in two short sentences."
        )
        print(result)
    finally:
        telemetry.flush()
        anthropic_openinference.deactivate()


if __name__ == "__main__":
    main()
