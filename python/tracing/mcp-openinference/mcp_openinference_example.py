#!/usr/bin/env python3
"""
MCP Client + OpenInference example for Respan tracing.

Uses openinference-instrumentation-mcp to propagate OTel context across
the MCP stdio transport boundary. The client creates a workflow span,
connects to an MCP server subprocess, and calls a tool. Because of the
instrumentation, the server's spans join the client's trace.
"""
import asyncio
import os
import sys
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

from openinference.instrumentation.mcp import MCPInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="mcp-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

mcp_oi = OpenInferenceInstrumentor(MCPInstrumentor)
mcp_oi.activate()

from mcp.client.stdio import stdio_client
from mcp.client.session import ClientSession
from mcp import StdioServerParameters


@workflow(name="mcp_openinference_workflow")
async def mcp_workflow() -> str:
    server_script = str(Path(__file__).parent / "mcp_server.py")
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_script],
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")

            result = await session.call_tool("get_haiku", {"topic": "recursion in programming"})
            text = result.content[0].text if result.content else ""
            return text


async def main() -> None:
    print("=" * 60)
    print("MCP OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = await mcp_workflow()
        print(result)
    finally:
        telemetry.flush()
        mcp_oi.deactivate()


if __name__ == "__main__":
    asyncio.run(main())
