#!/usr/bin/env python3
"""
Complex Edge-Case Tracing — Anthropic SDK features through Respan.

Exercises native Anthropic SDK capabilities to stress-test the Respan
OpenInference instrumentation:

  1. messages.create()          — basic, multi-turn, system prompt variants
  2. messages.stream()          — streaming with text_stream and get_final_message
  3. messages.count_tokens()    — pre-flight token estimation
  4. messages.parse()           — structured output via Pydantic model
  5. Tool use (tool_choice)     — auto / any / specific-tool forcing
  6. Agentic tool loop          — multi-round tool_use → tool_result cycling
  7. Prompt caching             — cache_control on system/messages
  8. Stop sequences             — custom stop tokens
  9. beta.messages.tool_runner() — SDK-managed automatic tool execution

Routes all calls through the Respan gateway.

Usage:
    python anthropic_complex_edge_cases_test.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Force this example to prefer the local Respan source tree over any published
# package already installed in the environment.
KEYWORDSAI_ROOT = Path(__file__).resolve().parents[4]
LOCAL_RESPAN_SOURCE_DIRS = (
    KEYWORDSAI_ROOT / "respan" / "python-sdks" / "respan-sdk" / "src",
    KEYWORDSAI_ROOT / "respan" / "python-sdks" / "respan-tracing" / "src",
    KEYWORDSAI_ROOT
    / "respan"
    / "python-sdks"
    / "instrumentations"
    / "respan-instrumentation-openinference"
    / "src",
)
for local_source_dir in reversed(LOCAL_RESPAN_SOURCE_DIRS):
    local_source_dir_str = str(local_source_dir)
    if local_source_dir.exists() and local_source_dir_str not in sys.path:
        sys.path.insert(0, local_source_dir_str)

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from anthropic import Anthropic
from anthropic.types import Message, TextBlock, ToolUseBlock
from openinference.instrumentation.anthropic import AnthropicInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry, get_client
from respan_tracing.decorators import task, tool, workflow
from respan_tracing.instruments import Instruments

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")
ANTHROPIC_GATEWAY_URL = f"{RESPAN_BASE_URL}/anthropic"
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
CUSTOMER_IDENTIFIER = "anthropic-complex-edge-cases-v2"

telemetry = RespanTelemetry(
    app_name="anthropic-complex-edge-cases",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    block_instruments={Instruments.ANTHROPIC, Instruments.REQUESTS, Instruments.URLLIB3},
)

anthropic_oi = OpenInferenceInstrumentor(AnthropicInstrumentor)
anthropic_oi.activate()

client = Anthropic(
    api_key=RESPAN_API_KEY or "test-key",
    base_url=ANTHROPIC_GATEWAY_URL,
)


# ═══════════════════════════════════════════════════════════════════════════
#  TOOL DEFINITIONS (native Anthropic format)
# ═══════════════════════════════════════════════════════════════════════════

WEATHER_TOOL = {
    "name": "get_weather",
    "description": "Get current weather for a city.",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"], "description": "Temperature unit"},
        },
        "required": ["city"],
    },
}

CALCULATOR_TOOL = {
    "name": "calculator",
    "description": "Evaluate a mathematical expression.",
    "input_schema": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression, e.g. '(12 + 8) * 3'"},
        },
        "required": ["expression"],
    },
}

SEARCH_TOOL = {
    "name": "web_search",
    "description": "Search the web for information on a topic.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "description": "Max results to return (1-5)"},
        },
        "required": ["query"],
    },
}

ALL_TOOLS = [WEATHER_TOOL, CALCULATOR_TOOL, SEARCH_TOOL]


@tool(name="get_weather")
def get_weather_tool(inputs: Dict[str, Any]) -> str:
    unit = inputs.get("unit", "celsius")
    temp = "22°C" if unit == "celsius" else "72°F"
    return json.dumps({
        "city": inputs["city"],
        "temp": temp,
        "condition": "Sunny",
        "humidity": "45%",
    })


@tool(name="calculator")
def calculator_tool(inputs: Dict[str, Any]) -> str:
    try:
        return str(eval(inputs["expression"]))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"


@tool(name="web_search")
def web_search_tool(inputs: Dict[str, Any]) -> str:
    return json.dumps([
        {
            "title": f"Result about {inputs['query']}",
            "snippet": f"Detailed info on {inputs['query']}...",
        },
        {
            "title": f"{inputs['query']} - Wikipedia",
            "snippet": "From the free encyclopedia...",
        },
    ])


def execute_tool(name: str, inputs: Dict[str, Any]) -> str:
    """Local tool dispatch — each concrete tool is individually traced."""
    if name == "get_weather":
        return get_weather_tool(inputs)
    if name == "calculator":
        return calculator_tool(inputs)
    if name == "web_search":
        return web_search_tool(inputs)
    return f"Unknown tool: {name}"


def _serialize_response_block(block: Any) -> Dict[str, Any]:
    """Convert Anthropic response blocks to JSON-safe dicts for task outputs."""
    if isinstance(block, TextBlock):
        return {
            "type": "text",
            "text": block.text,
        }
    if isinstance(block, ToolUseBlock):
        return {
            "type": "tool_use",
            "id": block.id,
            "name": block.name,
            "input": block.input,
        }
    return {
        "type": getattr(block, "type", block.__class__.__name__),
        "value": str(block),
    }


def _execute_tool_use_blocks(
    blocks: List[Any],
    *,
    print_prefix: str,
) -> List[Dict[str, Any]]:
    """Execute tool-use blocks and return JSON-safe results keyed by tool_use_id."""
    executed_tools: List[Dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, ToolUseBlock):
            continue
        result = execute_tool(block.name, block.input)
        print(f"    {print_prefix}{block.name}({json.dumps(block.input)}) → {result}")
        executed_tools.append({
            "tool_use_id": block.id,
            "name": block.name,
            "input": block.input,
            "result": result,
        })
    return executed_tools


def _build_tool_result_blocks(
    executed_tools: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Convert executed tool outputs into Anthropic tool_result content blocks."""
    return [
        {
            "type": "tool_result",
            "tool_use_id": tool_result["tool_use_id"],
            "content": tool_result["result"],
        }
        for tool_result in executed_tools
        if tool_result.get("tool_use_id")
    ]


def _summarize_message_response(
    resp: Message,
    *,
    executed_tools: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Return a compact JSON-safe summary for task span outputs."""
    executed_tool_map = {
        tool_result["tool_use_id"]: tool_result
        for tool_result in executed_tools or []
        if tool_result.get("tool_use_id")
    }
    serialized_content: List[Dict[str, Any]] = []
    for block in resp.content:
        block_summary = _serialize_response_block(block)
        block_id = block_summary.get("id")
        if isinstance(block_id, str) and block_id in executed_tool_map:
            block_summary["result"] = executed_tool_map[block_id]["result"]
        serialized_content.append(block_summary)

    summary = {
        "id": resp.id,
        "model": resp.model,
        "role": resp.role,
        "stop_reason": resp.stop_reason,
        "content": serialized_content,
    }
    if executed_tools:
        summary["executed_tools"] = executed_tools
    return summary


def _run_tool_choice_to_completion(
    *,
    messages: List[Dict[str, Any]],
    tool_choice: Dict[str, Any],
    max_tokens: int,
    print_prefix: str,
    max_rounds: int = 5,
) -> Dict[str, Any]:
    """Run a tool-choice scenario through tool execution and final assistant reply."""
    conversation_messages = list(messages)
    round_summaries: List[Dict[str, Any]] = []
    executed_tools: List[Dict[str, Any]] = []

    for round_index in range(max_rounds):
        request_kwargs: Dict[str, Any] = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": max_tokens,
            "tools": ALL_TOOLS,
            "messages": conversation_messages,
        }
        if round_index == 0:
            request_kwargs["tool_choice"] = tool_choice

        resp = client.messages.create(**request_kwargs)
        print(
            f"    Round {round_index + 1}: stop_reason={resp.stop_reason}, "
            f"blocks={len(resp.content)}"
        )

        for block in resp.content:
            if isinstance(block, TextBlock):
                label = "Final" if resp.stop_reason != "tool_use" else "Text"
                print(f"    {label}: {block.text[:150]}")

        round_executed_tools = _execute_tool_use_blocks(
            resp.content,
            print_prefix=print_prefix,
        )
        executed_tools.extend(round_executed_tools)
        round_summaries.append(
            _summarize_message_response(
                resp,
                executed_tools=round_executed_tools,
            )
        )

        if resp.stop_reason != "tool_use":
            break

        tool_result_blocks = _build_tool_result_blocks(round_executed_tools)
        if not tool_result_blocks:
            break

        conversation_messages.append({"role": "assistant", "content": resp.content})
        conversation_messages.append({"role": "user", "content": tool_result_blocks})

    final_stop_reason = (
        round_summaries[-1]["stop_reason"]
        if round_summaries
        else None
    )
    result = {
        "completed": final_stop_reason not in {None, "tool_use", "max_tokens"},
        "tool_choice": tool_choice,
        "rounds": round_summaries,
    }
    if executed_tools:
        result["executed_tools"] = executed_tools
    if round_summaries:
        result["final_response"] = round_summaries[-1]
    if final_stop_reason == "max_tokens":
        result["warning"] = "final_response_truncated"
    return result


# ═══════════════════════════════════════════════════════════════════════════
#  STRUCTURED OUTPUT MODEL (for messages.parse)
# ═══════════════════════════════════════════════════════════════════════════

class CityAnalysis(BaseModel):
    city: str = Field(description="City name")
    weather_summary: str = Field(description="Brief weather description")
    recommendation: str = Field(description="Travel recommendation")
    score: float = Field(description="Attractiveness score 0-10", ge=0, le=10)


# ═══════════════════════════════════════════════════════════════════════════
#  SCENARIO RUNNER
# ═══════════════════════════════════════════════════════════════════════════

def run_scenario(name: str, fn):
    print(f"\n{'─' * 60}")
    print(f"  SCENARIO: {name}")
    print(f"{'─' * 60}")
    try:
        fn()
        print(f"  ✓ {name} completed")
    except Exception as e:
        print(f"  ✗ {name} — {type(e).__name__}: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════

# --- 1. Basic messages.create() ---
@task(name="basic_create")
def scenario_basic_create():
    """Simplest messages.create() — single user message, no tools."""
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=50,
        messages=[{"role": "user", "content": "What is 2+2? Answer with just the number."}],
    )
    print(f"    Output: {resp.content[0].text}")
    print(f"    Model: {resp.model}, Stop: {resp.stop_reason}")
    print(f"    Tokens: {resp.usage.input_tokens}→{resp.usage.output_tokens}")


# --- 2. System prompt — string form ---
@task(name="system_prompt_string")
def scenario_system_string():
    """System prompt as a plain string."""
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=80,
        system="You are a pirate captain. Always start with 'Arrr!'",
        messages=[{"role": "user", "content": "What's your ship called?"}],
    )
    print(f"    Output: {resp.content[0].text}")


# --- 3. System prompt — multi-block array ---
@task(name="system_prompt_blocks")
def scenario_system_blocks():
    """System prompt as an array of TextBlockParam — tests structured system input."""
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=80,
        system=[
            {"type": "text", "text": "You are a helpful assistant."},
            {"type": "text", "text": "You always respond in exactly one sentence."},
            {"type": "text", "text": "You end every response with an exclamation mark."},
        ],
        messages=[{"role": "user", "content": "What is the tallest mountain?"}],
    )
    print(f"    Output: {resp.content[0].text}")


# --- 4. messages.stream() — streaming response ---
@task(name="streaming")
def scenario_streaming():
    """messages.stream() with text_stream iterator and get_final_message()."""
    chunks = []
    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=100,
        messages=[{"role": "user", "content": "Write a haiku about tracing."}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)
        final = stream.get_final_message()

    full_text = "".join(chunks)
    print(f"    Streamed ({len(chunks)} chunks): {full_text}")
    print(f"    Final message tokens: {final.usage.input_tokens}→{final.usage.output_tokens}")


# --- 5. messages.count_tokens() — token estimation ---
@task(name="count_tokens")
def scenario_count_tokens():
    """count_tokens() before calling create() — tests non-generation API spans.
    Falls back gracefully if the gateway doesn't support the endpoint."""
    messages = [{"role": "user", "content": "Explain quantum computing in three sentences."}]

    try:
        token_count = client.messages.count_tokens(
            model=ANTHROPIC_MODEL,
            messages=messages,
        )
        print(f"    Estimated input tokens: {token_count.input_tokens}")
    except Exception as e:
        print(f"    count_tokens not supported by gateway ({type(e).__name__}), skipping estimation")

    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=150,
        messages=messages,
    )
    print(f"    Actual tokens: {resp.usage.input_tokens}→{resp.usage.output_tokens}")
    print(f"    Output: {resp.content[0].text[:120]}")


# --- 6. Tool use — tool_choice: auto (model decides) ---
@task(name="tool_choice_auto")
def scenario_tool_choice_auto():
    """tool_choice=auto — model may or may not use tools."""
    return _run_tool_choice_to_completion(
        messages=[{"role": "user", "content": "What's the weather in Tokyo?"}],
        tool_choice={"type": "auto"},
        max_tokens=200,
        print_prefix="Tool call: ",
    )


# --- 7. Tool use — tool_choice: any (force tool use) ---
@task(name="tool_choice_any")
def scenario_tool_choice_any():
    """tool_choice=any — forces the model to call at least one tool."""
    return _run_tool_choice_to_completion(
        messages=[{"role": "user", "content": "Hello, how are you?"}],
        tool_choice={"type": "any"},
        max_tokens=200,
        print_prefix="Forced tool: ",
    )


# --- 8. Tool use — tool_choice: tool (force specific tool) ---
@task(name="tool_choice_specific")
def scenario_tool_choice_specific():
    """tool_choice=tool — forces a specific tool regardless of message content."""
    return _run_tool_choice_to_completion(
        messages=[{"role": "user", "content": "What's the meaning of life?"}],
        tool_choice={"type": "tool", "name": "calculator"},
        max_tokens=400,
        print_prefix="Forced calculator: ",
    )


# --- 9. Agentic tool loop — multi-round tool_use → tool_result ---
@task(name="agentic_tool_loop")
def scenario_agentic_loop():
    """Full agentic loop: model calls tools, we return results, repeat until end_turn.
    Tests multi-round message accumulation and tool_result serialization."""
    messages: list = [{"role": "user", "content": (
        "I need three things: "
        "1) Weather in Paris, "
        "2) Calculate 15% tip on $84.50, "
        "3) Search for 'best restaurants in Paris'. "
        "Use the tools for each."
    )}]
    system = "You have access to tools. Use them to answer precisely."

    rounds = 0
    while rounds < 5:
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=500,
            system=system,
            tools=ALL_TOOLS,
            messages=messages,
        )
        rounds += 1
        print(f"    Round {rounds}: stop_reason={resp.stop_reason}, blocks={len(resp.content)}")

        if resp.stop_reason != "tool_use":
            for block in resp.content:
                if isinstance(block, TextBlock):
                    print(f"    Final: {block.text[:150]}")
            break

        round_executed_tools = _execute_tool_use_blocks(
            resp.content,
            print_prefix="→ ",
        )
        tool_results = _build_tool_result_blocks(round_executed_tools)

        messages.append({"role": "assistant", "content": resp.content})
        messages.append({"role": "user", "content": tool_results})


# --- 10. Multi-turn conversation ---
@task(name="multi_turn_conversation")
def scenario_multi_turn():
    """Multi-turn conversation — tests growing message history across calls."""
    messages: list = []
    turns = [
        "My name is Alex and I love hiking.",
        "What's my name and hobby? Prove you remember.",
        "Suggest a hiking destination.",
    ]
    for user_msg in turns:
        messages.append({"role": "user", "content": user_msg})
        resp = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=100,
            messages=messages,
        )
        reply = resp.content[0].text
        messages.append({"role": "assistant", "content": reply})
        print(f"    User: {user_msg}")
        print(f"    Claude: {reply[:100]}")


# --- 11. Streaming with tool use ---
@task(name="streaming_with_tools")
def scenario_streaming_tools():
    """messages.stream() with tools — tests streamed tool_use blocks."""
    chunks = []
    with client.messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=200,
        tools=[WEATHER_TOOL],
        messages=[{"role": "user", "content": "What's the weather in London?"}],
    ) as stream:
        for text in stream.text_stream:
            chunks.append(text)
        final = stream.get_final_message()

    has_tool_use = any(isinstance(b, ToolUseBlock) for b in final.content)
    print(f"    Stop reason: {final.stop_reason}")
    print(f"    Has tool_use: {has_tool_use}")
    if has_tool_use:
        for block in final.content:
            if isinstance(block, ToolUseBlock):
                print(f"    Tool: {block.name}({json.dumps(block.input)})")
    if chunks:
        print(f"    Text chunks: {''.join(chunks)[:100]}")


# --- 12. Stop sequences ---
@task(name="stop_sequences")
def scenario_stop_sequences():
    """Custom stop_sequences — tests that stop_reason='stop_sequence' is captured."""
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=200,
        stop_sequences=["STOP", "END"],
        messages=[{"role": "user", "content": (
            "Count from 1 to 10, with each number on a new line. "
            "After the number 5, write the word STOP."
        )}],
    )
    print(f"    Stop reason: {resp.stop_reason}")
    print(f"    Stop sequence: {resp.stop_sequence}")
    print(f"    Output: {resp.content[0].text[:100]}")


# --- 13. Structured output via messages.parse() ---
@task(name="structured_output_parse")
def scenario_structured_output():
    """messages.parse() with a Pydantic model — tests structured output extraction."""
    resp = client.messages.parse(
        model=ANTHROPIC_MODEL,
        max_tokens=300,
        output_format=CityAnalysis,
        messages=[{"role": "user", "content": "Analyze Tokyo as a travel destination."}],
    )
    parsed = resp.parsed_output
    if parsed:
        print(f"    City: {parsed.city}")
        print(f"    Weather: {parsed.weather_summary}")
        print(f"    Score: {parsed.score}/10")
        print(f"    Recommendation: {parsed.recommendation[:100]}")
    else:
        print(f"    Raw output: {resp.content[0].text[:150]}")


# --- 14. Prompt caching ---
@task(name="prompt_caching")
def scenario_prompt_caching():
    """Prompt caching via cache_control on system and messages.
    Second call should show cache_read_input_tokens > 0."""
    long_system = (
        "You are an expert literary analyst. You have deep knowledge of "
        "world literature spanning from ancient texts to modern novels. "
        "You provide detailed, scholarly analysis with references to "
        "specific works, authors, and literary movements. " * 20
    )

    cached_system = [{"type": "text", "text": long_system, "cache_control": {"type": "ephemeral"}}]
    messages = [{"role": "user", "content": "Name one famous novel."}]

    resp1 = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=60,
        system=cached_system,
        messages=messages,
    )
    print(f"    Call 1 — input: {resp1.usage.input_tokens}, "
          f"cache_create: {resp1.usage.cache_creation_input_tokens}, "
          f"cache_read: {resp1.usage.cache_read_input_tokens}")
    print(f"    Output: {resp1.content[0].text[:80]}")

    resp2 = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=60,
        system=cached_system,
        messages=[{"role": "user", "content": "Name another famous novel, different from before."}],
    )
    print(f"    Call 2 — input: {resp2.usage.input_tokens}, "
          f"cache_create: {resp2.usage.cache_creation_input_tokens}, "
          f"cache_read: {resp2.usage.cache_read_input_tokens}")
    print(f"    Output: {resp2.content[0].text[:80]}")


# --- 15. Multi-content-block input ---
@task(name="multi_block_input")
def scenario_multi_block_input():
    """User message with multiple text content blocks."""
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=100,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Context: The Eiffel Tower is 330m tall."},
                {"type": "text", "text": "Context: It was built in 1889."},
                {"type": "text", "text": "Question: How tall is the Eiffel Tower and when was it built?"},
            ],
        }],
    )
    print(f"    Output: {resp.content[0].text}")


# --- 16. Temperature and top_p variants ---
@task(name="sampling_params")
def scenario_sampling_params():
    """Different temperature and top_k settings — tests parameter capture in spans."""
    for temp, top_k in [(0.0, None), (1.0, 40)]:
        kwargs: Dict[str, Any] = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": 30,
            "temperature": temp,
            "messages": [{"role": "user", "content": "Pick a random color. One word."}],
        }
        if top_k is not None:
            kwargs["top_k"] = top_k
        resp = client.messages.create(**kwargs)
        print(f"    temp={temp}, top_k={top_k}: {resp.content[0].text}")


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════

@workflow(name="anthropic_complex_edge_cases_v2")
def main_workflow():
    rc = get_client()
    if rc:
        rc.update_current_span(
            respan_params={
                "customer_identifier": CUSTOMER_IDENTIFIER,
                "metadata": {
                    "test_suite": "anthropic_complex_edge_cases_v2",
                    "gateway_model": ANTHROPIC_MODEL,
                },
            }
        )

    # Core messages API
    run_scenario("1. Basic messages.create()", scenario_basic_create)
    run_scenario("2. System prompt (string)", scenario_system_string)
    run_scenario("3. System prompt (multi-block)", scenario_system_blocks)
    run_scenario("4. messages.stream()", scenario_streaming)
    run_scenario("5. messages.count_tokens()", scenario_count_tokens)

    # Tool use variants
    run_scenario("6. Tool use — tool_choice: auto", scenario_tool_choice_auto)
    run_scenario("7. Tool use — tool_choice: any", scenario_tool_choice_any)
    run_scenario("8. Tool use — tool_choice: specific", scenario_tool_choice_specific)
    run_scenario("9. Agentic tool loop (multi-round)", scenario_agentic_loop)

    # Advanced features
    run_scenario("10. Multi-turn conversation", scenario_multi_turn)
    run_scenario("11. Streaming with tools", scenario_streaming_tools)
    run_scenario("12. Stop sequences", scenario_stop_sequences)
    run_scenario("13. Structured output (messages.parse)", scenario_structured_output)
    run_scenario("14. Prompt caching", scenario_prompt_caching)
    run_scenario("15. Multi-block input", scenario_multi_block_input)
    run_scenario("16. Sampling params (temperature/top_p)", scenario_sampling_params)


def main() -> None:
    print("=" * 60)
    print("  ANTHROPIC COMPLEX EDGE-CASE TRACING TEST v2")
    print("  Native SDK feature stress test")
    print("=" * 60)
    print(f"  Gateway:  {ANTHROPIC_GATEWAY_URL}")
    print(f"  Model:    {ANTHROPIC_MODEL}")
    print(f"  API key:  {RESPAN_API_KEY[:8] if RESPAN_API_KEY else '(not set)'}...")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    start = time.time()
    try:
        main_workflow()
    finally:
        elapsed = time.time() - start
        print(f"\n{'=' * 60}")
        print(f"  ALL SCENARIOS COMPLETE — {elapsed:.1f}s elapsed")
        print(f"  Flushing telemetry...")
        print(f"{'=' * 60}")
        telemetry.flush()
        anthropic_oi.deactivate()
        print("\n  Done! Check Respan dashboard for the trace.")


if __name__ == "__main__":
    main()
