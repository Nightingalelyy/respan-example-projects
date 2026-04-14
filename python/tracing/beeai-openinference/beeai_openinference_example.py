#!/usr/bin/env python3
"""
BeeAI Framework + OpenInference example for Respan tracing.

Uses openinference-instrumentation-beeai to auto-instrument BeeAI's
ReActAgent and exports spans to Respan via the respan-instrumentation-openinference wrapper.

BeeAI Framework provides a ReAct agent that reasons and acts in a loop,
automatically producing tool-use spans and LLM chat spans.
"""
import asyncio
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

from openinference.instrumentation.beeai import BeeAIInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="beeai-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

beeai_oi = OpenInferenceInstrumentor(BeeAIInstrumentor)
beeai_oi.activate()

from beeai_framework.adapters.openai.backend.chat import OpenAIChatModel
from beeai_framework.agents.react import ReActAgent
from beeai_framework.memory.unconstrained_memory import UnconstrainedMemory


@workflow(name="beeai_openinference_workflow")
async def beeai_workflow(topic: str) -> str:
    llm = OpenAIChatModel(
        model_id="gpt-4o-mini",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
    )

    agent = ReActAgent(
        llm=llm,
        tools=[],
        memory=UnconstrainedMemory(),
    )

    result = await agent.run(f"Write a haiku about {topic}. Output ONLY the haiku.")
    return result.output[-1].text if result.output else ""


async def main() -> None:
    print("=" * 60)
    print("BeeAI OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = await beeai_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        beeai_oi.deactivate()


if __name__ == "__main__":
    asyncio.run(main())
