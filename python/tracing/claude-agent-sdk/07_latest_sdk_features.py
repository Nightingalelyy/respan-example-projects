"""Exercise latest SDK options, structured output and background-task termination."""
import asyncio

from _shared import FakeClaudeTransport, ToolSpec, run_example


class LatestTransport(FakeClaudeTransport):
    async def _enqueue_tool_hook(self, event_name):
        if event_name != "PostToolUse":
            return await super()._enqueue_tool_hook(event_name)
        await self._queue.put({
            "type": "system", "subtype": "task_started", "task_id": "fixture-task",
            "tool_use_id": "tool-1", "description": "Read fixture", "uuid": "start",
            "session_id": self._session_id, "task_type": "local_agent",
        })
        await self._queue.put({
            "type": "system", "subtype": "task_updated", "task_id": "fixture-task",
            "patch": {"status": "completed"}, "uuid": "complete", "session_id": self._session_id,
        })
        await self._enqueue_final_response()

    async def _enqueue_final_response(self):
        await self._queue.put({
            "type": "result", "subtype": "success", "duration_ms": 1,
            "duration_api_ms": 1, "is_error": False, "num_turns": 1,
            "session_id": self._session_id, "structured_output": {"answer": 42},
            "modelUsage": {"claude-sonnet-4-5": {"inputTokens": 9, "outputTokens": 3,
                "cacheReadInputTokens": 2, "cacheCreationInputTokens": 0}},
        })
        await self._queue.put(None)


if __name__ == "__main__":
    asyncio.run(run_example(
        example_name="07_latest_sdk_features", prompts=["@literal /literal structured task"],
        tools=[ToolSpec("Agent", {"prompt": "Read fixture"}, "completed")],
        transport_class=LatestTransport,
        option_overrides={"verbatim_prompts": True, "include_partial_messages": True,
            "output_format": {"type": "json_schema", "schema": {"type": "object"}}},
    ))
