#!/usr/bin/env python3
"""CrewAI global LLM and tool hooks."""

from __future__ import annotations

from typing import Any

from common import print_raw_result, start_respan


HOOK_EVENTS: list[str] = []


def main() -> None:
    settings, respan = start_respan(
        "crewai-global-hooks",
        metadata={"example": "crewai-global-hooks"},
    )
    clear_all_global_hooks = None
    try:
        from crewai import Agent, Crew, Task
        from crewai.hooks import (
            after_llm_call,
            after_tool_call,
            before_llm_call,
            before_tool_call,
            clear_after_llm_call_hooks,
            clear_all_global_hooks as clear_hooks,
        )
        from crewai.tools import tool

        clear_all_global_hooks = clear_hooks

        @before_llm_call
        def record_before_llm(context: Any) -> bool | None:
            agent = getattr(context, "agent", None)
            HOOK_EVENTS.append(f"before_llm:{getattr(agent, 'role', 'unknown')}")
            return None

        @after_llm_call
        def record_after_llm(context: Any) -> str | None:
            response = getattr(context, "response", "")
            HOOK_EVENTS.append(f"after_llm:{len(response)}")
            return None

        @before_tool_call
        def record_before_tool(context: Any) -> bool | None:
            HOOK_EVENTS.append(f"before_tool:{getattr(context, 'tool_name', 'unknown')}")
            return None

        @after_tool_call
        def record_after_tool(context: Any) -> str | None:
            result = getattr(context, "tool_result", "")
            HOOK_EVENTS.append(f"after_tool:{len(str(result))}")
            return None

        @tool("service_status_lookup")
        def service_status_lookup(service: str) -> str:
            """Return a simple status summary for a service."""
            return f"{service}: degraded, owner=payments-platform"

        llm_agent = Agent(
            role="Hooked Summary Writer",
            goal="Return a concise hook validation sentence.",
            backstory="You validate global LLM hooks without using tools.",
            llm=settings.model,
            verbose=True,
        )
        llm_task = Task(
            description="Write one sentence that says CrewAI LLM hooks ran.",
            expected_output="One sentence.",
            agent=llm_agent,
        )
        llm_result = Crew(agents=[llm_agent], tasks=[llm_task], verbose=True).kickoff()

        clear_after_llm_call_hooks()

        tool_agent = Agent(
            role="Hooked Service Analyst",
            goal="Use a tool and let CrewAI hooks observe the run.",
            backstory="You validate hook callbacks around LLM and tool calls.",
            tools=[service_status_lookup],
            llm=settings.model,
            verbose=True,
        )
        task = Task(
            description=(
                "Call service_status_lookup for checkout and return the status "
                "exactly from the tool."
            ),
            expected_output="The checkout status and owner.",
            agent=tool_agent,
        )
        result = Crew(agents=[tool_agent], tasks=[task], verbose=True).kickoff()

        required_events = ("after_llm:", "before_tool:", "after_tool:")
        missing_events = [
            event_prefix
            for event_prefix in required_events
            if not any(event.startswith(event_prefix) for event in HOOK_EVENTS)
        ]
        if missing_events:
            raise RuntimeError(f"Missing hook events: {', '.join(missing_events)}")

        print_raw_result("CrewAI global hooks LLM result", llm_result)
        print_raw_result("CrewAI global hooks result", result)
        print("\n=== Hook events ===")
        for event in HOOK_EVENTS:
            print(event)
    finally:
        if clear_all_global_hooks is not None:
            clear_all_global_hooks()
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
