"""Opt-in live Chat request, separate from deterministic error/stream cases."""

from respan import workflow

from _shared import (
    example_attributes,
    finish_respan,
    live_enabled,
    load_root_env,
    make_respan,
    make_sync_client,
    model_name,
    print_result,
)

load_root_env()
if not live_enabled():
    raise RuntimeError("Set RESPAN_OPENAI_LIVE=1 to opt into a real provider request")
EXAMPLE = "live-provider"
respan = make_respan(EXAMPLE)


@workflow(name="openai_live_provider")
def run() -> str:
    response = client.chat.completions.create(
        model=model_name(),
        messages=[
            {
                "role": "user",
                "content": "Reply with: OpenAI instrumentation is working.",
            }
        ],
    )
    assert response.choices[0].message.content
    return response.choices[0].message.content


try:
    client = make_sync_client()
    try:
        with example_attributes(EXAMPLE):
            print_result(EXAMPLE, run())
    finally:
        client.close()
finally:
    finish_respan(respan)
