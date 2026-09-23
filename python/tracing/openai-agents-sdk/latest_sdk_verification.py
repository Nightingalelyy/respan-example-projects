"""Run real latest-SDK features, export to Respan, then verify IDs through MCP."""

import asyncio
import json
import os
import uuid
from types import SimpleNamespace
import sys
from pathlib import Path
from importlib.metadata import version

from agents import (
    Agent,
    Runner,
    RunConfig,
    ModelSettings,
    OpenAIChatCompletionsModel,
    function_tool,
    input_guardrail,
    GuardrailFunctionOutput,
    InputGuardrailTripwireTriggered,
    SQLiteSession,
)
from agents.exceptions import UserError
from agents.mcp import MCPServerStdio
from agents.tracing import (
    trace,
    response_span,
    mcp_tools_span,
    speech_group_span,
    transcription_span,
    speech_span,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic import BaseModel
from respan import Respan
from respan_instrumentation_openai_agents import OpenAIAgentsInstrumentor

load_dotenv(os.environ.get("RESPAN_ENV_FILE", ".env"), override=False)
marker = os.environ.get(
    "RESPAN_EXAMPLE_RUN_ID", f"openai-py-latest-{uuid.uuid4().hex[:12]}"
)


@function_tool
def forecast(city: str) -> str:
    """Return the verified weather for a city."""
    return f"Sunny in {city}; 22 C."


@function_tool(needs_approval=True)
def approve_action(note: str) -> str:
    """Execute the user-approved sample action."""
    return f"Approved: {note}"


@input_guardrail(run_in_parallel=False)
async def block(ctx, agent, value):
    return GuardrailFunctionOutput(
        output_info={"reason": "verification"}, tripwire_triggered=True
    )


class Answer(BaseModel):
    city: str
    weather: str


async def main():
    respan = Respan(
        api_key=os.environ["RESPAN_API_KEY"],
        app_name="openai-agents-latest-python",
        instrumentations=[OpenAIAgentsInstrumentor()],
        is_auto_instrument=False,
    )
    client = AsyncOpenAI(
        api_key=os.environ.get("RESPAN_GATEWAY_API_KEY", os.environ["RESPAN_API_KEY"]),
        base_url=os.environ.get("RESPAN_GATEWAY_BASE_URL", "https://api.respan.ai/api"),
        timeout=45,
        max_retries=0,
    )
    model = OpenAIChatCompletionsModel(
        model=os.environ.get("RESPAN_MODEL", "gpt-4o-mini"), openai_client=client
    )
    records = []

    async def scenario(name, action):
        selected = os.environ.get("RESPAN_SCENARIOS")
        if selected and name not in selected.split(","):
            return
        with trace(
            f"openai-py-latest.{name}",
            group_id=marker,
            metadata={"run_id": marker, "scenario": name},
        ) as t:
            result = await action()
        records.append({"scenario": name, "sdk_trace_id": t.trace_id, "result": result})
        respan.flush()
        print(json.dumps(records[-1]), flush=True)

    async def tools_stream():
        agent = Agent(
            name="Weather",
            model=model,
            instructions="Always call forecast for Paris then report the result.",
            tools=[forecast],
        )
        result = Runner.run_streamed(agent, "What is the weather in Paris?")
        events = 0
        async for _ in result.stream_events():
            events += 1
        assert "Paris" in result.final_output and events > 0
        return {"output": result.final_output, "events": events}

    async def handoff():
        specialist = Agent(
            name="Specialist", model=model, instructions="Reply: specialist verified."
        )
        agent = Agent(
            name="Triage",
            model=model,
            instructions="Always transfer to Specialist immediately.",
            handoffs=[specialist],
        )
        result = await Runner.run(agent, "Transfer to Specialist.")
        assert result.last_agent.name == "Specialist"
        return result.final_output

    async def structured_session():
        session = SQLiteSession(marker)
        agent = Agent(name="Structured", model=model, output_type=Answer)
        first = await Runner.run(
            agent, "Remember the city Paris and sunny weather.", session=session
        )
        second = await Runner.run(
            agent, "Repeat the city and weather from before.", session=session
        )
        assert second.final_output.city == "Paris"
        return second.final_output.model_dump()

    async def guardrail():
        try:
            await Runner.run(
                Agent(name="Blocked", model=model, input_guardrails=[block]),
                "Block this test.",
            )
        except InputGuardrailTripwireTriggered:
            return {"expected_error": "InputGuardrailTripwireTriggered"}
        raise AssertionError("guardrail did not trigger")

    async def approval():
        agent = Agent(
            name="Approval",
            model=model,
            instructions="Call approve_action with note verify once, then return the result.",
            tools=[approve_action],
        )
        first = await Runner.run(agent, "Execute the sample action.")
        assert first.interruptions
        state = first.to_state()
        for item in first.interruptions:
            state.approve(item)
        result = await Runner.run(agent, state)
        assert not result.interruptions
        return result.final_output

    async def tool_error():
        @function_tool(failure_error_function=None)
        def fail() -> str:
            """Raise the expected verification error."""
            raise RuntimeError("Expected verification tool failure")

        try:
            await Runner.run(
                Agent(
                    name="Failure",
                    model=model,
                    instructions="Always call fail.",
                    tools=[fail],
                ),
                "Call fail now.",
            )
        except UserError as exc:
            assert "Expected verification tool failure" in str(exc)
            return {"expected_error": str(exc)}
        raise AssertionError("tool error did not happen")

    async def mcp():
        async with MCPServerStdio(
            name="verification-weather",
            params={
                "command": sys.executable,
                "args": [str(Path(__file__).with_name("verification_mcp_server.py"))],
            },
        ) as server:
            agent = Agent(
                name="MCP Weather",
                model=model,
                instructions="Always call forecast_mcp for Paris then report the result.",
                mcp_servers=[server],
            )
            result = await Runner.run(
                agent, "Use the MCP tool to get weather for Paris."
            )
            assert "Paris" in result.final_output
            return result.final_output

    async def native_hosted():
        with response_span() as span:
            span.span_data.input = [{"role": "user", "content": "Hosted fixture"}]
            span.span_data.response = SimpleNamespace(
                model="gpt-4o-mini",
                tools=[],
                usage=None,
                output=[
                    {
                        "type": "file_search_call",
                        "id": "fs_fixture",
                        "queries": ["hello"],
                    },
                    {
                        "type": "code_interpreter_call",
                        "id": "ci_fixture",
                        "code": "print(42)",
                        "container_id": "c",
                        "outputs": [{"type": "logs", "logs": "42"}],
                    },
                    {
                        "type": "image_generation_call",
                        "id": "img_fixture",
                        "revised_prompt": "cat",
                        "result": "BASE64",
                    },
                ],
            )
        return {"mode": "native SDK hosted response payload fixture"}

    async def privacy_sdk():
        result = await Runner.run(
            Agent(
                name="Private",
                model=model,
                tools=[forecast],
                instructions="Call forecast for Paris then report the result.",
            ),
            "PRIVATE_CONTENT: weather in Paris?",
            run_config=RunConfig(trace_include_sensitive_data=False),
        )
        return {"completed": bool(result.final_output)}

    async def native_voice_mcp():
        # SDK tracing surfaces are deterministic; no hosted audio API is invoked.
        with mcp_tools_span(server="weather", result=["forecast"]):
            pass
        with speech_group_span(input="Hello"):
            with transcription_span(
                input="YXVkaW8=", input_format="pcm", output="Hello", model="whisper-1"
            ):
                pass
            with speech_span(
                input="Hello", output="YXVkaW8=", output_format="pcm", model="tts-1"
            ):
                pass
        return {"mode": "native SDK tracing surface"}

    try:
        for name, action in [
            ("tools_stream", tools_stream),
            ("handoff", handoff),
            ("structured_session", structured_session),
            ("guardrail", guardrail),
            ("approval", approval),
            ("tool_error", tool_error),
            ("mcp", mcp),
            ("privacy_sdk", privacy_sdk),
            ("native_hosted", native_hosted),
            ("native_voice_mcp", native_voice_mcp),
        ]:
            await scenario(name, action)
    finally:
        respan.flush()
        await client.close()
        respan.shutdown()
    print(
        json.dumps(
            {
                "run_id": marker,
                "sdk_version": version("openai-agents"),
                "records": records,
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
