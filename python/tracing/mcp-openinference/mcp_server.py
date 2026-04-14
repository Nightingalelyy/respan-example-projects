#!/usr/bin/env python3
"""
MCP Server that exposes a "get_haiku" tool.

Runs as a subprocess, communicating via stdio transport.
The MCPInstrumentor propagates OTel context from the client
across the stdio boundary so server spans join the client's trace.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY") or ""
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")

from openinference.instrumentation.mcp import MCPInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

provider = TracerProvider()
provider.add_span_processor(
    SimpleSpanProcessor(
        OTLPSpanExporter(
            endpoint=f"{RESPAN_BASE_URL}/v2/traces",
            headers={"Authorization": f"Bearer {RESPAN_API_KEY}"},
        )
    )
)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("mcp-server")

MCPInstrumentor().instrument()

from mcp.server.fastmcp import FastMCP
import openai

mcp = FastMCP("haiku-server")


@mcp.tool()
def get_haiku(topic: str) -> str:
    """Generate a haiku about the given topic using an LLM."""
    with tracer.start_as_current_span("llm_call") as span:
        span.set_attribute("gen_ai.request.model", "gpt-4o-mini")
        client = openai.OpenAI(api_key=RESPAN_API_KEY, base_url=RESPAN_BASE_URL)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": f"Write a haiku about {topic}. Output ONLY the haiku."}],
            temperature=0,
            max_tokens=64,
        )
        result = response.choices[0].message.content or ""
        span.set_attribute("gen_ai.response.model", response.model)
        return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
