#!/usr/bin/env python3
"""
Complex Claude Agent SDK example using the local Respan instrumentation plugin.

Covers:
1. Basic one-shot query()
2. Single-tool query() with Claude MCP tools
3. Multi-tool query() with chained tool usage
4. Tool error handling
5. Stateful ClaudeSDKClient multi-turn session with tools

Run:
    python complex_edge_cases_test.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import claude_agent_sdk  # type: ignore[reportMissingImports]
from claude_agent_sdk import (  # type: ignore[reportMissingImports]
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
    tool as claude_tool,
)
from dotenv import load_dotenv
from respan import Respan  # type: ignore[reportMissingImports]
from respan_instrumentation_claude_agent_sdk import (  # type: ignore[reportMissingImports]
    ClaudeAgentSDKInstrumentor as RespanClaudeAgentSDKInstrumentor,
)
from respan_tracing.decorators import task, workflow

EXAMPLE_REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_PATH = EXAMPLE_REPO_ROOT / ".env"
EXAMPLE_CWD = Path(__file__).resolve().parent


def _load_example_env() -> Path | None:
    if ROOT_ENV_PATH.exists():
        load_dotenv(ROOT_ENV_PATH, override=True)
        return ROOT_ENV_PATH
    load_dotenv(override=True)
    return None


LOADED_ENV_PATH = _load_example_env()

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
CLAUDE_AGENT_MODEL = os.getenv("CLAUDE_AGENT_MODEL", "sonnet")
CUSTOMER_IDENTIFIER = "claude-agent-sdk-complex-edge-cases-v2"
ANTHROPIC_GATEWAY_URL = f"{RESPAN_BASE_URL}/anthropic"

if not RESPAN_API_KEY:
    raise RuntimeError(
        "RESPAN_GATEWAY_API_KEY or RESPAN_API_KEY must be set in the repo-root .env."
    )

os.environ.setdefault("ANTHROPIC_API_KEY", RESPAN_API_KEY)
os.environ.setdefault("ANTHROPIC_AUTH_TOKEN", RESPAN_API_KEY)
os.environ.setdefault("ANTHROPIC_BASE_URL", ANTHROPIC_GATEWAY_URL)


@claude_tool(
    "get_weather",
    "Get current weather information for a city.",
    {"city": str, "unit": str},
)
async def get_weather_tool(args: dict[str, Any]) -> dict[str, Any]:
    unit = args.get("unit", "celsius")
    temperature = "22C" if unit == "celsius" else "72F"
    payload = {
        "city": args["city"],
        "temperature": temperature,
        "condition": "Sunny",
        "humidity": "45%",
    }
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


@claude_tool(
    "calculator",
    "Evaluate a mathematical expression and return the numeric result.",
    {"expression": str},
)
async def calculator_tool(args: dict[str, Any]) -> dict[str, Any]:
    try:
        result = str(eval(args["expression"]))  # noqa: S307
    except Exception as exc:
        return {
            "content": [{"type": "text", "text": f"Calculator error: {exc}"}],
            "is_error": True,
        }
    return {"content": [{"type": "text", "text": result}]}


@claude_tool(
    "web_search",
    "Return a short mock search result list for a query.",
    {"query": str, "max_results": int},
)
async def web_search_tool(args: dict[str, Any]) -> dict[str, Any]:
    results = [
        {
            "title": f"Result about {args['query']}",
            "snippet": f"Detailed info on {args['query']}...",
        },
        {
            "title": f"{args['query']} - Wikipedia",
            "snippet": "From the free encyclopedia...",
        },
    ]
    max_results = max(1, min(int(args.get("max_results", 2)), len(results)))
    return {"content": [{"type": "text", "text": json.dumps(results[:max_results])}]}


@claude_tool(
    "lookup_customer_profile",
    "Look up a customer profile and return an error for unknown IDs.",
    {"customer_id": str},
)
async def lookup_customer_profile_tool(args: dict[str, Any]) -> dict[str, Any]:
    customer_id = args["customer_id"]
    if customer_id != "cust_123":
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Customer {customer_id} was not found in the demo CRM.",
                }
            ],
            "is_error": True,
        }

    payload = {
        "customer_id": customer_id,
        "plan": "enterprise",
        "health": "green",
        "renewal_month": "2026-09",
    }
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


DEMO_TOOL_NAMES = [
    "get_weather",
    "calculator",
    "web_search",
    "lookup_customer_profile",
]
DEMO_MCP_SERVER = create_sdk_mcp_server(
    name="respan_demo_tools",
    version="1.0.0",
    tools=[
        get_weather_tool,
        calculator_tool,
        web_search_tool,
        lookup_customer_profile_tool,
    ],
)

TOOL_SYSTEM_PROMPT = (
    "You have access to demo MCP tools. "
    "When the user asks for information that a tool can provide, call the tool "
    "before answering. Keep the final answer concise."
)
MULTI_TOOL_SYSTEM_PROMPT = (
    "You have access to demo MCP tools. "
    "If the user asks for multiple facts that map to multiple tools, call every "
    "relevant tool before giving the final answer."
)


def _build_options(
    *,
    include_demo_tools: bool = False,
    system_prompt: str | None = None,
    max_turns: int = 4,
) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model=CLAUDE_AGENT_MODEL,
        max_turns=max_turns,
        permission_mode="bypassPermissions",
        cwd=str(EXAMPLE_CWD),
        env={
            "ANTHROPIC_API_KEY": RESPAN_API_KEY,
            "ANTHROPIC_AUTH_TOKEN": RESPAN_API_KEY,
            "ANTHROPIC_BASE_URL": ANTHROPIC_GATEWAY_URL,
        },
        system_prompt=system_prompt,
        mcp_servers={"demo": DEMO_MCP_SERVER} if include_demo_tools else {},
        allowed_tools=DEMO_TOOL_NAMES if include_demo_tools else [],
    )


def _serialize_content_block(block: Any) -> dict[str, Any]:
    if isinstance(block, TextBlock):
        return {"type": "text", "text": block.text}
    if isinstance(block, ToolUseBlock):
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    if isinstance(block, ToolResultBlock):
        return {
            "type": "tool_result",
            "tool_use_id": block.tool_use_id,
            "content": block.content,
            "is_error": block.is_error,
        }
    return {"type": block.__class__.__name__, "value": str(block)}


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for block in content:
        if isinstance(block, TextBlock):
            text_parts.append(block.text)
        elif isinstance(block, ToolResultBlock) and isinstance(block.content, str):
            text_parts.append(block.content)
    return "\n".join(part for part in text_parts if part)


def _serialize_system_message(message: SystemMessage) -> dict[str, Any]:
    data = getattr(message, "data", {}) or {}
    summary: dict[str, Any] = {
        "type": "system",
        "subtype": message.subtype,
    }
    for key in ("session_id", "model", "cwd", "permission_mode"):
        if key in data:
            summary[key] = data[key]
    if "usage" in data:
        summary["usage"] = data["usage"]
    return summary


def _serialize_message(message: Any) -> dict[str, Any]:
    if isinstance(message, AssistantMessage):
        return {
            "type": "assistant",
            "model": message.model,
            "content": [_serialize_content_block(block) for block in message.content],
        }
    if isinstance(message, UserMessage):
        serialized_content = (
            [_serialize_content_block(block) for block in message.content]
            if isinstance(message.content, list)
            else message.content
        )
        return {
            "type": "user",
            "content": serialized_content,
            "parent_tool_use_id": message.parent_tool_use_id,
            "tool_use_result": message.tool_use_result,
            "uuid": message.uuid,
        }
    if isinstance(message, SystemMessage):
        return _serialize_system_message(message)
    if isinstance(message, ResultMessage):
        return {
            "type": "result",
            "subtype": message.subtype,
            "duration_ms": message.duration_ms,
            "duration_api_ms": message.duration_api_ms,
            "is_error": message.is_error,
            "num_turns": message.num_turns,
            "session_id": message.session_id,
            "stop_reason": message.stop_reason,
            "total_cost_usd": message.total_cost_usd,
            "usage": message.usage,
            "result": message.result,
        }
    return {"type": type(message).__name__, "value": str(message)}


def _print_stream_message(message: Any) -> None:
    if isinstance(message, SystemMessage):
        print(f"    [System] subtype={message.subtype}")
        return

    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(f"    [Assistant] {block.text[:160]}")
            elif isinstance(block, ToolUseBlock):
                print(f"    [ToolUse] {block.name}({json.dumps(block.input)})")
            elif isinstance(block, ToolResultBlock):
                print(
                    "    [ToolResultBlock] "
                    f"{block.tool_use_id} -> {_extract_text_from_content([block])[:120]}"
                )
        return

    if isinstance(message, UserMessage) and message.parent_tool_use_id:
        content_text = _extract_text_from_content(message.content)
        print(
            "    [UserToolResult] "
            f"{message.parent_tool_use_id}: {content_text[:160]}"
        )
        return

    if isinstance(message, ResultMessage):
        print(
            "    [Result] "
            f"subtype={message.subtype}, stop={message.stop_reason}, "
            f"turns={message.num_turns}, session={message.session_id}"
        )
        if message.result:
            print(f"    [ResultText] {message.result[:160]}")
        return

    print(f"    [{type(message).__name__}]")


async def _run_query_collect(
    *,
    prompt: str,
    options: ClaudeAgentOptions,
) -> dict[str, Any]:
    message_types: list[str] = []
    serialized_messages: list[dict[str, Any]] = []
    result_summary: dict[str, Any] | None = None

    async for message in claude_agent_sdk.query(prompt=prompt, options=options):
        _print_stream_message(message)
        message_types.append(type(message).__name__)
        serialized = _serialize_message(message)
        serialized_messages.append(serialized)
        if isinstance(message, ResultMessage):
            result_summary = serialized

    return {
        "prompt": prompt,
        "message_types": message_types,
        "messages": serialized_messages,
        "result": result_summary,
    }


async def _collect_client_turn(
    *,
    client: ClaudeSDKClient,
    prompt: str,
    session_id: str,
) -> dict[str, Any]:
    print(f"    [User] {prompt}")
    await client.query(prompt, session_id=session_id)

    message_types: list[str] = []
    serialized_messages: list[dict[str, Any]] = []
    result_summary: dict[str, Any] | None = None

    async for message in client.receive_response():
        _print_stream_message(message)
        message_types.append(type(message).__name__)
        serialized = _serialize_message(message)
        serialized_messages.append(serialized)
        if isinstance(message, ResultMessage):
            result_summary = serialized

    return {
        "prompt": prompt,
        "message_types": message_types,
        "messages": serialized_messages,
        "result": result_summary,
    }


async def _run_scenario(name: str, fn) -> dict[str, Any]:
    print(f"\n{'-' * 60}")
    print(f"  SCENARIO: {name}")
    print(f"{'-' * 60}")
    result = await fn()
    print(f"  completed: {name}")
    return result


@task(name="basic_query")
async def scenario_basic_query() -> dict[str, Any]:
    return await _run_query_collect(
        prompt="Explain in two short sentences what Claude Agent SDK tracing gives me.",
        options=_build_options(max_turns=2),
    )


@task(name="single_tool_query")
async def scenario_single_tool_query() -> dict[str, Any]:
    return await _run_query_collect(
        prompt=(
            "Use the get_weather tool to check Tokyo weather, then summarize the "
            "result in two bullet points."
        ),
        options=_build_options(
            include_demo_tools=True,
            system_prompt=TOOL_SYSTEM_PROMPT,
            max_turns=4,
        ),
    )


@task(name="multi_tool_query")
async def scenario_multi_tool_query() -> dict[str, Any]:
    return await _run_query_collect(
        prompt=(
            "Use get_weather for Paris, calculator for 84.50 * 0.15, and web_search "
            "for best restaurants in Paris. Then give me a concise trip summary."
        ),
        options=_build_options(
            include_demo_tools=True,
            system_prompt=MULTI_TOOL_SYSTEM_PROMPT,
            max_turns=6,
        ),
    )


@task(name="tool_error_query")
async def scenario_tool_error_query() -> dict[str, Any]:
    return await _run_query_collect(
        prompt=(
            "Use the lookup_customer_profile tool for customer_id cust_404 and "
            "tell me briefly what happened."
        ),
        options=_build_options(
            include_demo_tools=True,
            system_prompt=TOOL_SYSTEM_PROMPT,
            max_turns=4,
        ),
    )


@task(name="client_multi_turn_with_tools")
async def scenario_client_multi_turn_with_tools() -> dict[str, Any]:
    session_id = "claude-agent-sdk-complex-session"
    options = _build_options(
        include_demo_tools=True,
        system_prompt=MULTI_TOOL_SYSTEM_PROMPT,
        max_turns=6,
    )
    turns: list[dict[str, Any]] = []

    async with ClaudeSDKClient(options=options) as client:
        mcp_status = await client.get_mcp_status()
        turns.append(
            await _collect_client_turn(
                client=client,
                prompt="Remember that my name is Alex and my favorite city is Kyoto.",
                session_id=session_id,
            )
        )
        turns.append(
            await _collect_client_turn(
                client=client,
                prompt=(
                    "What are my name and favorite city? Use get_weather for Kyoto "
                    "and answer briefly."
                ),
                session_id=session_id,
            )
        )
        turns.append(
            await _collect_client_turn(
                client=client,
                prompt=(
                    "Use web_search to find one popular attraction in Kyoto and "
                    "recommend it in one sentence."
                ),
                session_id=session_id,
            )
        )
        turns.append(
            await _collect_client_turn(
                client=client,
                prompt=(
                    "Use lookup_customer_profile for customer_id cust_404 and "
                    "tell me briefly what happened."
                ),
                session_id=session_id,
            )
        )
        turns.append(
            await _collect_client_turn(
                client=client,
                prompt=(
                    "Now use calculator for 120 * 0.15 and answer in one sentence "
                    "with the tip amount."
                ),
                session_id=session_id,
            )
        )

    return {
        "session_id": session_id,
        "mcp_status": mcp_status,
        "turns": turns,
    }


@workflow(name="claude_agent_sdk_complex_edge_cases")
async def run_complex_workflow() -> dict[str, Any]:
    return {
        "basic_query": await scenario_basic_query(),
        "single_tool_query": await scenario_single_tool_query(),
        "multi_tool_query": await scenario_multi_tool_query(),
        "tool_error_query": await scenario_tool_error_query(),
        "client_multi_turn_with_tools": await scenario_client_multi_turn_with_tools(),
    }


def _print_summary(results: dict[str, Any]) -> None:
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Customer identifier: {CUSTOMER_IDENTIFIER}")
    print(f"Base URL:            {RESPAN_BASE_URL}")
    print(f"Anthropic URL:       {ANTHROPIC_GATEWAY_URL}")
    print(f"Claude model:        {CLAUDE_AGENT_MODEL}")
    print(f"Loaded .env:         {LOADED_ENV_PATH or 'find_dotenv fallback'}")
    print()

    for scenario_name, scenario_result in results.items():
        if scenario_name == "client_multi_turn_with_tools":
            print(
                f"- {scenario_name}: {len(scenario_result['turns'])} turns, "
                f"session={scenario_result['session_id']}"
            )
            continue

        result_summary = scenario_result.get("result") or {}
        print(
            f"- {scenario_name}: "
            f"messages={len(scenario_result.get('messages', []))}, "
            f"session={result_summary.get('session_id')}, "
            f"stop={result_summary.get('stop_reason')}"
        )

    print("\nCheck traces in Respan with:")
    print(f"  customer_identifier = {CUSTOMER_IDENTIFIER}")
    print("  metadata.example_name = claude_agent_sdk_complex_edge_cases")


async def main() -> None:
    respan = Respan(
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
        app_name="claude-agent-sdk-complex-edge-cases",
        instrumentations=[
            RespanClaudeAgentSDKInstrumentor(
                agent_name="claude-agent-sdk-complex-edge-cases",
                capture_content=True,
            )
        ],
        metadata={
            "example_name": "claude_agent_sdk_complex_edge_cases",
            "sdk": "claude-agent-sdk",
            "local_instrumentation": True,
        },
        environment=os.getenv("RESPAN_ENVIRONMENT"),
    )

    try:
        with respan.propagate_attributes(customer_identifier=CUSTOMER_IDENTIFIER):
            results = await run_complex_workflow()
        _print_summary(results)
    finally:
        respan.flush()


if __name__ == "__main__":
    asyncio.run(main())
