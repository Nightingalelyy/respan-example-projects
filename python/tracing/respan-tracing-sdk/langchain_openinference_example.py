#!/usr/bin/env python3
"""
LangChain + OpenInference example for Respan tracing.

This example shows the explicit LangChain tracing path:
1. Initialize `RespanTelemetry`
2. Activate `OpenInferenceInstrumentor(LangChainInstrumentor)`
3. Build and invoke a normal LangChain pipeline
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from openinference.instrumentation.langchain import LangChainInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry, get_client
from respan_tracing.decorators import task, workflow

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")
ANTHROPIC_GATEWAY_URL = f"{RESPAN_BASE_URL}/anthropic"
LANGCHAIN_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
HAS_RESPAN_API_KEY = bool(RESPAN_API_KEY)

telemetry = RespanTelemetry(
    app_name="langchain-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    # Keep this example on the explicit OpenInference wrapper path.
    instruments=set(),
)

langchain_openinference = OpenInferenceInstrumentor(LangChainInstrumentor)
langchain_openinference.activate()


def build_langchain_chain():
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a concise assistant. Answer in exactly two sentences."),
            ("human", "Explain {topic} for a backend engineer. Mention tracing and spans."),
        ]
    )
    llm = ChatAnthropic(
        model_name=LANGCHAIN_MODEL,
        api_key=RESPAN_API_KEY or "test-key",
        base_url=ANTHROPIC_GATEWAY_URL,
        temperature=0,
        max_tokens_to_sample=120,
    )
    return prompt | llm | StrOutputParser()


@task(name="langchain_chain_invoke")
def run_langchain_chain(topic: str) -> str:
    chain = build_langchain_chain()
    return chain.invoke({"topic": topic})


@workflow(name="langchain_openinference_workflow")
def langchain_openinference_workflow(topic: str) -> str:
    client = get_client()
    if client:
        client.update_current_span(
            respan_params={
                "customer_identifier": "langchain-openinference-example",
                "metadata": {
                    "example_name": "langchain_openinference_example",
                    "gateway_model": LANGCHAIN_MODEL,
                    "provider": "anthropic-via-langchain",
                },
            }
        )
    return run_langchain_chain(topic=topic)


def main() -> None:
    print("=" * 60)
    print("LangChain OpenInference Example")
    print("=" * 60)

    if not HAS_RESPAN_API_KEY:
        print("Skipping live run because RESPAN_API_KEY is not set in the example repo root .env.")
        return

    try:
        result = langchain_openinference_workflow(
            topic="OpenInference instrumentation with LangChain"
        )
        print(result)
    finally:
        telemetry.flush()
        langchain_openinference.deactivate()


if __name__ == "__main__":
    main()
