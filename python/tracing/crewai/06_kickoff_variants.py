#!/usr/bin/env python3
"""CrewAI kickoff variants: sync, async, native async, and for-each."""

from __future__ import annotations

import asyncio

from common import print_raw_result, start_respan


def build_crew(model: str):
    from crewai import Agent, Crew, Task

    agent = Agent(
        role="Kickoff Variant Reporter",
        goal="Return concise status summaries for different kickoff paths.",
        backstory="You validate CrewAI execution entry points for observability tests.",
        llm=model,
        verbose=False,
    )
    task = Task(
        description=(
            "Write one sentence explaining why the {variant} entry point is useful "
            "when testing CrewAI tracing."
        ),
        expected_output="One sentence mentioning the variant name.",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], verbose=False)


async def run_async_variants(model: str) -> tuple[object, object, list[object]]:
    kickoff_async_output = await build_crew(model).kickoff_async(
        inputs={"variant": "kickoff_async"}
    )
    native_async_output = await build_crew(model).akickoff(
        inputs={"variant": "akickoff"}
    )
    foreach_async_outputs = await build_crew(model).kickoff_for_each_async(
        inputs=[
            {"variant": "kickoff_for_each_async input A"},
            {"variant": "kickoff_for_each_async input B"},
        ]
    )
    return kickoff_async_output, native_async_output, list(foreach_async_outputs)


def main() -> None:
    settings, respan = start_respan(
        "crewai-kickoff-variants",
        metadata={"example": "crewai-kickoff-variants"},
    )
    try:
        sync_output = build_crew(settings.model).kickoff(inputs={"variant": "kickoff"})
        foreach_outputs = build_crew(settings.model).kickoff_for_each(
            inputs=[
                {"variant": "kickoff_for_each input A"},
                {"variant": "kickoff_for_each input B"},
            ]
        )
        kickoff_async_output, native_async_output, foreach_async_outputs = asyncio.run(
            run_async_variants(settings.model)
        )

        print_raw_result("kickoff", sync_output)
        print_raw_result("kickoff_async", kickoff_async_output)
        print_raw_result("akickoff", native_async_output)
        for index, output in enumerate(foreach_outputs, start=1):
            print_raw_result(f"kickoff_for_each #{index}", output)
        for index, output in enumerate(foreach_async_outputs, start=1):
            print_raw_result(f"kickoff_for_each_async #{index}", output)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
