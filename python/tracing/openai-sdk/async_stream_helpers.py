"""Async complete and early-close helpers keep every stream span bounded."""

import asyncio

from respan import workflow

from _shared import (
    example_attributes,
    finish_respan,
    make_async_client,
    make_respan,
    model_name,
    print_result,
)

EXAMPLE = "async-stream-helpers"
respan = make_respan(EXAMPLE)


@workflow(name="openai_async_stream_helpers")
async def run() -> str:
    messages = [{"role": "user", "content": "Write a Python haiku."}]
    async with client.chat.completions.stream(
        model=model_name(), messages=messages
    ) as stream:
        result = await stream.get_final_completion()
        assert result.choices[0].message.content
    async with client.chat.completions.stream(
        model=model_name(), messages=messages
    ) as stream:
        async for event in stream:
            if event.type == "content.delta":
                assert event.delta
                break
    async with client.responses.stream(
        model=model_name(), input="Write a Python haiku."
    ) as stream:
        result = await stream.get_final_response()
        assert result.output_text
    async with client.responses.stream(
        model=model_name(), input="Write a Python haiku."
    ) as stream:
        async for event in stream:
            if event.type == "response.output_text.delta":
                assert event.delta
                break
    async with await client.responses.create(
        model=model_name(), input="Write a Python haiku.", stream=True
    ) as stream:
        async for event in stream:
            if event.type == "response.output_text.delta":
                assert event.delta
                break
    return "completed=5; partial streams preserve observed text without invented usage"


async def main() -> None:
    try:
        global client
        client = make_async_client()
        try:
            with example_attributes(EXAMPLE):
                print_result(EXAMPLE, await run())
        finally:
            await client.close()
    finally:
        finish_respan(respan)


asyncio.run(main())
