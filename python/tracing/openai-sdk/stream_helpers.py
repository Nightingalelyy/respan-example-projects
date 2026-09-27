"""Complete and early-close streaming helpers with the actual OpenAI SDK."""

from respan import workflow

from _shared import (
    example_attributes,
    finish_respan,
    make_respan,
    make_sync_client,
    model_name,
    print_result,
)

EXAMPLE = "stream-helpers"
respan = make_respan(EXAMPLE)


@workflow(name="openai_stream_helpers")
def run() -> str:
    messages = [{"role": "user", "content": "Write a Python haiku."}]
    with client.chat.completions.stream(
        model=model_name(), messages=messages
    ) as stream:
        assert stream.get_final_completion().choices[0].message.content
    with client.chat.completions.stream(
        model=model_name(), messages=messages
    ) as stream:
        for event in stream:
            if event.type == "content.delta":
                assert event.delta
                break
    with client.responses.stream(
        model=model_name(), input="Write a Python haiku."
    ) as stream:
        assert stream.get_final_response().output_text
    with client.responses.stream(
        model=model_name(), input="Write a Python haiku."
    ) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                assert event.delta
                break
    with client.responses.create(
        model=model_name(), input="Write a Python haiku.", stream=True
    ) as stream:
        for event in stream:
            if event.type == "response.output_text.delta":
                assert event.delta
                break
    return "completed=5; partial streams preserve observed text without invented usage"


try:
    client = make_sync_client()
    try:
        with example_attributes(EXAMPLE):
            print_result(EXAMPLE, run())
    finally:
        client.close()
finally:
    finish_respan(respan)
