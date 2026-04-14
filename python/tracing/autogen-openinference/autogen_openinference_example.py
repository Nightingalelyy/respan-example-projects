#!/usr/bin/env python3
"""
AutoGen AgentChat + OpenInference example for Respan tracing.

Uses openinference-instrumentation-autogen-agentchat to auto-instrument AutoGen
and exports spans to Respan via the respan-instrumentation-openinference wrapper.
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from openinference.instrumentation.autogen_agentchat import AutogenAgentChatInstrumentor
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
    app_name="autogen-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

autogen_openinference = OpenInferenceInstrumentor(AutogenAgentChatInstrumentor)
autogen_openinference.activate()


@workflow(name="autogen_openinference_workflow")
async def autogen_openinference_workflow(prompt: str) -> str:
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",
        base_url=RESPAN_BASE_URL,
        api_key=RESPAN_API_KEY,
    )

    agent = AssistantAgent(
        name="haiku_agent",
        model_client=model_client,
        system_message="You are a helpful assistant. Respond only with a haiku.",
    )

    result = await Console(agent.run_stream(task=prompt))
    await model_client.close()
    return result.messages[-1].content


async def main() -> None:
    print("=" * 60)
    print("AutoGen AgentChat OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = await autogen_openinference_workflow(
            prompt="Write a haiku about recursion in programming."
        )
        print(f"\nFinal result: {result}")
    finally:
        telemetry.flush()
        autogen_openinference.deactivate()


if __name__ == "__main__":
    asyncio.run(main())
