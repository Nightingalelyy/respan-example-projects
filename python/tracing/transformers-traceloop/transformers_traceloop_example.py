#!/usr/bin/env python3
"""
HuggingFace Transformers + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-transformers (Traceloop) to auto-instrument
the HuggingFace Transformers library and exports spans to Respan.

This example runs a tiny GPT-2 model locally (no API calls needed) and
traces the text generation pipeline call.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")

from opentelemetry.instrumentation.transformers import TransformersInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="transformers-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

TransformersInstrumentor().instrument()

from transformers import pipeline

generator = pipeline(
    "text-generation",
    model="sshleifer/tiny-gpt2",
    device=-1,
)


@workflow(name="transformers_traceloop_workflow")
def transformers_workflow(prompt: str) -> str:
    results = generator(
        prompt,
        max_new_tokens=50,
        do_sample=False,
    )
    return results[0]["generated_text"]


def main() -> None:
    print("=" * 60)
    print("HuggingFace Transformers Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    result = transformers_workflow(prompt="The meaning of recursion is")
    print(f"Generated text:\n{result}")

    telemetry.flush()


if __name__ == "__main__":
    main()
