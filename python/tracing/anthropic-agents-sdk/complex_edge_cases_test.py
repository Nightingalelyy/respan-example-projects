#!/usr/bin/env python3
"""
Complex edge cases for the official Anthropic Python SDK routed through the
Respan gateway and traced with the local Respan Anthropic instrumentor.

Covered SDK entry points:
- `client.messages.create(...)`
- `client.messages.create(..., stream=True)`
- `client.messages.stream(...).text_stream + get_final_message()`
- Messages API tool use with `tools` + `tool_choice` + `tool_result`
- Expected invalid-model request error handling

Run:
    python complex_edge_cases_test.py

    # or with pytest
    pytest complex_edge_cases_test.py -v -s
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv
from respan import Respan, task, workflow
from respan_instrumentation_anthropic import AnthropicInstrumentor

EXAMPLE_REPO_ROOT = Path(__file__).resolve().parents[3]
ROOT_ENV_PATH = EXAMPLE_REPO_ROOT / ".env"

EXAMPLE_NAME = "anthropic_sdk_complex_edge_cases"
CUSTOMER_IDENTIFIER = "anthropic-sdk-complex-edge-cases-v1"
APP_NAME = "anthropic-sdk-complex-edge-cases"

WEATHER_TOOL = {
    "name": "get_weather",
    "description": "Get current weather information for a city.",
    "input_schema": {
        "type": "object",
        "properties": {
            "city": {"type": "string"},
            "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
        },
        "required": ["city"],
    },
}

CUSTOMER_TOOL = {
    "name": "lookup_customer_profile",
    "description": "Look up a customer profile and return plan status information.",
    "input_schema": {
        "type": "object",
        "properties": {
            "customer_id": {"type": "string"},
        },
        "required": ["customer_id"],
    },
}

CLIENT: Anthropic | None = None


def _load_example_env() -> Path | None:
    if ROOT_ENV_PATH.exists():
        load_dotenv(ROOT_ENV_PATH, override=True)
        return ROOT_ENV_PATH
    load_dotenv(override=True)
    return None


LOADED_ENV_PATH = _load_example_env()

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_BASE_URL")
    or os.getenv("RESPAN_GATEWAY_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")
RESPAN_GATEWAY_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL") or RESPAN_BASE_URL
).rstrip("/")
ANTHROPIC_BASE_URL = (
    os.getenv("ANTHROPIC_BASE_URL") or f"{RESPAN_GATEWAY_BASE_URL}/anthropic"
).rstrip("/")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


def _require_respan_api_key() -> str:
    if RESPAN_API_KEY:
        return RESPAN_API_KEY
    raise RuntimeError(
        "Set RESPAN_GATEWAY_API_KEY or RESPAN_API_KEY in the example repo root .env."
    )


def _get_client() -> Anthropic:
    if CLIENT is None:
        raise RuntimeError("Anthropic client is not initialized. Call main() first.")
    return CLIENT


def _serialize_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    return value


def _extract_text(content: list[Any]) -> str:
    text_parts: list[str] = []
    for block in content:
        if getattr(block, "type", None) == "text" and getattr(block, "text", None):
            text_parts.append(block.text)
    return "\n".join(text_parts).strip()


def _extract_tool_use_blocks(message: Any) -> list[Any]:
    tool_uses: list[Any] = []
    for block in getattr(message, "content", []) or []:
        if getattr(block, "type", None) == "tool_use":
            tool_uses.append(block)
    return tool_uses


def _summarize_tool_uses(message: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": block.id,
            "name": block.name,
            "input": _serialize_value(block.input),
        }
        for block in _extract_tool_use_blocks(message)
    ]


def _summarize_message(message: Any) -> dict[str, Any]:
    return {
        "id": getattr(message, "id", None),
        "model": str(getattr(message, "model", "")),
        "stop_reason": getattr(message, "stop_reason", None),
        "text": _extract_text(getattr(message, "content", []) or []),
        "usage": _serialize_value(getattr(message, "usage", None)),
        "tool_uses": _summarize_tool_uses(message),
    }


def _assistant_content_to_params(content: list[Any]) -> list[dict[str, Any]]:
    params: list[dict[str, Any]] = []

    for block in content:
        block_type = getattr(block, "type", None)
        if block_type == "text":
            params.append({"type": "text", "text": block.text})
            continue

        if block_type == "tool_use":
            params.append(
                {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": _serialize_value(block.input),
                }
            )

    return params


def _build_weather_result(input_data: dict[str, Any]) -> str:
    city = str(input_data.get("city", "unknown"))
    unit = (
        "fahrenheit"
        if input_data.get("unit") == "fahrenheit"
        else "celsius"
    )
    temperature = "72F" if unit == "fahrenheit" else "22C"
    return json.dumps(
        {
            "city": city,
            "temperature": temperature,
            "condition": "Sunny",
            "humidity": "45%",
        }
    )


def _build_customer_result(input_data: dict[str, Any]) -> dict[str, Any]:
    customer_id = str(input_data.get("customer_id", "unknown"))
    if customer_id != "cust_123":
        return {
            "content": f"Customer {customer_id} was not found in the demo CRM.",
            "is_error": True,
        }

    return {
        "content": json.dumps(
            {
                "customer_id": customer_id,
                "plan": "enterprise",
                "health": "green",
                "renewal_month": "2026-09",
            }
        )
    }


def _execute_demo_tool(tool_use: Any) -> dict[str, Any]:
    input_data = (
        _serialize_value(getattr(tool_use, "input", {}))
        if isinstance(getattr(tool_use, "input", {}), dict)
        else {}
    )

    if tool_use.name == WEATHER_TOOL["name"]:
        return {"content": _build_weather_result(input_data)}

    if tool_use.name == CUSTOMER_TOOL["name"]:
        return _build_customer_result(input_data)

    return {
        "content": f"Unsupported tool: {tool_use.name}",
        "is_error": True,
    }


def _build_tool_result_blocks(tool_uses: list[Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for tool_use in tool_uses:
        result = _execute_demo_tool(tool_use)
        block = {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": result["content"],
        }
        if result.get("is_error"):
            block["is_error"] = True
        blocks.append(block)
    return blocks


def _snippet(value: str, max_length: int = 160) -> str:
    return value if len(value) <= max_length else f"{value[:max_length]}..."


@task(name="messages_create_basic")
def run_basic_create() -> dict[str, Any]:
    message = _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=160,
        system=[{"type": "text", "text": "You are terse and precise."}],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "In one sentence, explain why tracing helps debugging.",
                    }
                ],
            }
        ],
    )
    summary = _summarize_message(message)
    print(f"  [basic] {_snippet(str(summary['text']))}")
    return summary


@task(name="messages_create_stream_true")
def run_streaming_create() -> dict[str, Any]:
    event_types: list[str] = []
    text_delta = ""

    with _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=180,
        stream=True,
        messages=[
            {
                "role": "user",
                "content": "Write a short haiku about instrumentation.",
            }
        ],
    ) as stream:
        for event in stream:
            event_types.append(getattr(event, "type", "unknown"))
            delta = getattr(event, "delta", None)
            if (
                getattr(event, "type", None) == "content_block_delta"
                and getattr(delta, "type", None) == "text_delta"
            ):
                text_delta += getattr(delta, "text", "")

    print(f"  [stream:true] events={' -> '.join(event_types)}")
    return {
        "event_types": event_types,
        "text_preview": _snippet(text_delta),
    }


@task(name="messages_stream_helper")
def run_stream_helper() -> dict[str, Any]:
    text_chunks: list[str] = []

    with _get_client().messages.stream(
        model=ANTHROPIC_MODEL,
        max_tokens=180,
        messages=[
            {
                "role": "user",
                "content": "List three trace debugging benefits as short bullets.",
            }
        ],
    ) as stream:
        for text_delta in stream.text_stream:
            text_chunks.append(text_delta)
        final_message = stream.get_final_message()

    summary = _summarize_message(final_message)
    print(f"  [messages.stream] {_snippet(str(summary['text']))}")
    return {
        "text_delta_count": len(text_chunks),
        "final_message": summary,
    }


@task(name="messages_create_tool_success_roundtrip")
def run_tool_success_roundtrip() -> dict[str, Any]:
    prompt = "Use the get_weather tool for Tokyo, then give me a short travel tip."
    initial = _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=220,
        tool_choice={"type": "tool", "name": WEATHER_TOOL["name"]},
        tools=[WEATHER_TOOL],
        messages=[{"role": "user", "content": prompt}],
    )

    tool_uses = _extract_tool_use_blocks(initial)
    if not tool_uses:
        raise RuntimeError("Expected get_weather tool_use block but none were returned.")

    tool_results = _build_tool_result_blocks(tool_uses)
    final_message = _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=220,
        tools=[WEATHER_TOOL],
        messages=[
            {"role": "user", "content": prompt},
            {
                "role": "assistant",
                "content": _assistant_content_to_params(initial.content),
            },
            {"role": "user", "content": tool_results},
        ],
    )

    summary = {
        "initial_message": _summarize_message(initial),
        "tool_results": tool_results,
        "final_message": _summarize_message(final_message),
    }
    final_text = str(summary["final_message"].get("text", ""))
    print(
        "  [tool success] "
        f"tool_results={len(tool_results)}, final={_snippet(final_text)}"
    )
    return summary


@task(name="messages_create_tool_error_roundtrip")
def run_tool_error_roundtrip() -> dict[str, Any]:
    prompt = (
        "Use lookup_customer_profile for customer_id cust_404 and explain what "
        "happened."
    )
    initial = _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=220,
        tool_choice={"type": "tool", "name": CUSTOMER_TOOL["name"]},
        tools=[CUSTOMER_TOOL],
        messages=[{"role": "user", "content": prompt}],
    )

    tool_uses = _extract_tool_use_blocks(initial)
    if not tool_uses:
        raise RuntimeError(
            "Expected lookup_customer_profile tool_use block but none were returned."
        )

    tool_results = _build_tool_result_blocks(tool_uses)
    final_message = _get_client().messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=220,
        tools=[CUSTOMER_TOOL],
        messages=[
            {"role": "user", "content": prompt},
            {
                "role": "assistant",
                "content": _assistant_content_to_params(initial.content),
            },
            {"role": "user", "content": tool_results},
        ],
    )

    summary = {
        "initial_message": _summarize_message(initial),
        "tool_results": tool_results,
        "final_message": _summarize_message(final_message),
    }
    final_text = str(summary["final_message"].get("text", ""))
    print(
        "  [tool error] "
        f"tool_results={len(tool_results)}, final={_snippet(final_text)}"
    )
    return summary


@task(name="messages_create_expected_error")
def run_expected_request_error() -> dict[str, Any]:
    try:
        _get_client().messages.create(
            model="claude-invalid-model",
            max_tokens=64,
            messages=[
                {
                    "role": "user",
                    "content": "This request should fail with an invalid model.",
                }
            ],
        )
    except Exception as error:  # noqa: BLE001 - example should surface SDK error text
        message = str(error)
        print(f"  [expected error] {_snippet(message)}")
        return {"error_message": message}

    return {"unexpected_success": True}


@workflow(name="anthropic_sdk_complex_edge_cases")
def run_workflow() -> dict[str, Any]:
    return {
        "messages_create_basic": run_basic_create(),
        "messages_create_stream_true": run_streaming_create(),
        "messages_stream_helper": run_stream_helper(),
        "messages_create_tool_success_roundtrip": run_tool_success_roundtrip(),
        "messages_create_tool_error_roundtrip": run_tool_error_roundtrip(),
        "messages_create_expected_error": run_expected_request_error(),
    }


def _print_summary(results: dict[str, Any]) -> None:
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Customer identifier: {CUSTOMER_IDENTIFIER}")
    print(f"Example name:        {EXAMPLE_NAME}")
    print(f"Model:               {ANTHROPIC_MODEL}")
    print(f"Respan base URL:     {RESPAN_BASE_URL}")
    print(f"Gateway base URL:    {RESPAN_GATEWAY_BASE_URL}")
    print(f"Anthropic base URL:  {ANTHROPIC_BASE_URL}")
    print(f"Loaded .env:         {LOADED_ENV_PATH or 'dotenv fallback'}")
    print()

    for name, value in results.items():
        record = value if isinstance(value, dict) else {}

        if name == "messages_create_stream_true":
            event_types = record.get("event_types")
            rendered_event_types = (
                " -> ".join(event_types)
                if isinstance(event_types, list)
                else "unknown"
            )
            print(f"- {name}: {rendered_event_types}")
            continue

        final_message = record.get("final_message")
        if isinstance(final_message, dict):
            print(
                f"- {name}: stop={final_message.get('stop_reason', 'unknown')}, "
                f"text={_snippet(str(final_message.get('text', '')))}"
            )
            continue

        if "error_message" in record:
            print(f"- {name}: {_snippet(str(record['error_message']))}")
            continue

        if "text" in record:
            print(
                f"- {name}: stop={record.get('stop_reason', 'unknown')}, "
                f"text={_snippet(str(record.get('text', '')))}"
            )
            continue

        print(f"- {name}: completed")

    print("\nCheck traces in Respan with:")
    print(f"  customer_identifier = {CUSTOMER_IDENTIFIER}")
    print(f"  metadata.example_name = {EXAMPLE_NAME}")


def main() -> dict[str, Any]:
    global CLIENT

    api_key = _require_respan_api_key()
    os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
    os.environ.setdefault("ANTHROPIC_BASE_URL", ANTHROPIC_BASE_URL)

    respan = Respan(
        api_key=api_key,
        base_url=RESPAN_BASE_URL,
        app_name=APP_NAME,
        instrumentations=[AnthropicInstrumentor()],
        metadata={
            "example_name": EXAMPLE_NAME,
            "sdk": "anthropic-python-sdk",
            "gateway_routed": True,
            "local_instrumentation": True,
            "example_type": "complex_edge_cases",
        },
        environment=os.getenv("RESPAN_ENVIRONMENT"),
    )
    CLIENT = Anthropic(
        api_key=api_key,
        base_url=ANTHROPIC_BASE_URL,
    )

    try:
        with respan.propagate_attributes(customer_identifier=CUSTOMER_IDENTIFIER):
            results = run_workflow()
        _print_summary(results)
        return results
    finally:
        respan.flush()


def test_complex_edge_cases() -> None:
    if not RESPAN_API_KEY:
        import pytest

        pytest.skip("Set RESPAN_GATEWAY_API_KEY or RESPAN_API_KEY to run.")
    results = main()
    assert "messages_create_basic" in results
    assert "messages_create_tool_success_roundtrip" in results
    assert "messages_create_expected_error" in results


if __name__ == "__main__":
    main()
