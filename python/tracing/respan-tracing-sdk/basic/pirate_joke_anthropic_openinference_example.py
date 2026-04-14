#!/usr/bin/env python3
"""
Anthropic workflow example instrumented through OpenInference for Respan.
"""
import os
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
from openinference.instrumentation.anthropic import AnthropicInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import task, workflow
from respan_tracing.instruments import Instruments

ROOT_ENV_PATH = Path(__file__).resolve().parents[4] / ".env"
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
    app_name="pirate-joke-anthropic-openinference",
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


@task(name="create_joke")
def create_joke() -> str:
    response = anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=120,
        messages=[
            {
                "role": "user",
                "content": "Tell me a short pirate joke about OpenTelemetry.",
            }
        ],
    )
    return response.content[0].text if response.content else ""


@task(name="ask_for_comments")
def ask_for_comments(joke: str) -> str:
    response = anthropic_client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=120,
        messages=[
            {
                "role": "user",
                "content": f"What do you think about this joke?\n\n{joke}",
            }
        ],
    )
    return response.content[0].text if response.content else ""


@task(name="present_result")
def present_result(joke: str, comments: str) -> str:
    return f"Joke:\n{joke}\n\nComments:\n{comments}"


@workflow(name="pirate_joke_with_anthropic_feedback")
def pirate_joke_with_anthropic_feedback() -> str:
    joke = create_joke()
    comments = ask_for_comments(joke=joke)
    return present_result(joke=joke, comments=comments)


def main() -> None:
    print("=" * 60)
    print("Pirate Joke Anthropic OpenInference Example")
    print("=" * 60)

    if not HAS_RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    try:
        print(pirate_joke_with_anthropic_feedback())
    finally:
        telemetry.flush()
        anthropic_openinference.deactivate()


if __name__ == "__main__":
    main()
