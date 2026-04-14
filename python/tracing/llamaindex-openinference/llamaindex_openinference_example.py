#!/usr/bin/env python3
"""
LlamaIndex + OpenInference example for Respan tracing.

Uses openinference-instrumentation-llama-index to auto-instrument LlamaIndex
and exports spans to Respan via the respan-instrumentation-openinference wrapper.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from llama_index.core.llms import ChatMessage
from llama_index.llms.openai import OpenAI
from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import task, workflow

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")
OPENAI_GATEWAY_URL = f"{RESPAN_BASE_URL}"

telemetry = RespanTelemetry(
    app_name="llamaindex-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

llamaindex_openinference = OpenInferenceInstrumentor(LlamaIndexInstrumentor)
llamaindex_openinference.activate()


@task(name="llamaindex_chat")
def run_llamaindex_chat(prompt: str) -> str:
    llm = OpenAI(
        model="gpt-4o-mini",
        api_key=RESPAN_API_KEY,
        api_base=OPENAI_GATEWAY_URL,
        temperature=0,
    )
    messages = [
        ChatMessage(role="system", content="You are a helpful assistant. Respond only with a haiku."),
        ChatMessage(role="user", content=prompt),
    ]
    response = llm.chat(messages)
    return str(response.message.content)


@workflow(name="llamaindex_openinference_workflow")
def llamaindex_openinference_workflow(prompt: str) -> str:
    return run_llamaindex_chat(prompt=prompt)


def main() -> None:
    print("=" * 60)
    print("LlamaIndex OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = llamaindex_openinference_workflow(
            prompt="Write a haiku about recursion in programming."
        )
        print(result)
    finally:
        telemetry.flush()
        llamaindex_openinference.deactivate()


if __name__ == "__main__":
    main()
