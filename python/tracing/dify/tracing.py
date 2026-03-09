#!/usr/bin/env python3
"""
Tracing — Compact workflow and task spans.

This example keeps the tree intentionally small:
Workflow -> Task -> LLM Call.

The prompt asks for a very short answer, and the workflow returns a compact
summary so the trace UI is easier to scan.
"""

import os
import uuid
from dotenv import load_dotenv
from dify_client.models import ChatRequest, ResponseMode
from respan_exporter_dify import create_client, flush_pending_exports
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow, task

# Load environment variables from .env
load_dotenv(override=True)

# 1. Initialize Telemetry globally
telemetry = RespanTelemetry(
    app_name="dify-tracing-example",
    api_key=os.getenv("RESPAN_API_KEY"),
)

respan_client = create_client(
    api_key=os.getenv("RESPAN_API_KEY", "your-respan-api-key"),
    gateway_base_url=os.getenv("RESPAN_BASE_URL"),
    gateway_model=os.getenv("RESPAN_MODEL"),
)

@task(name="prepare_request")
def prepare_request(topic: str) -> ChatRequest:
    """Create a short prompt so the trace output stays compact."""
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    return ChatRequest(
        query=f"Answer with exactly 5 words: what is {topic}?",
        user=user_id,
        response_mode=ResponseMode.BLOCKING,
        inputs={},
    )

@workflow(name="dify_simple_trace")
def run_simple_trace(topic: str) -> dict[str, str]:
    """Run one task plus one LLM call for a compact trace tree."""
    print(f"Starting simple trace for: {topic}")

    req = prepare_request(topic)

    print("Calling Respan Gateway...")
    response = respan_client.chat_messages(req=req)

    short_answer = " ".join(response.answer.split())
    print("\nWorkflow completed.")
    return {
        "topic": topic,
        "answer": short_answer,
    }

def main():
    try:
        result = run_simple_trace("distributed tracing")
        print("\nFinal Output:")
        print(f"{result['topic']}: {result['answer']}")
    finally:
        # Important: flush telemetry to ensure all spans are exported before exiting
        telemetry.flush()
        flush_pending_exports(timeout=20)

if __name__ == "__main__":
    main()
