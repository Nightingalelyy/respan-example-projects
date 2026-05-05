#!/usr/bin/env python3
"""CrewAI LiteAgent example."""

from __future__ import annotations

import asyncio

from common import print_raw_result, start_respan


async def run_async_lite_agent(agent: object) -> object:
    return await agent.kickoff_async(
        "In one sentence, explain why LiteAgent is useful for a tracing smoke test."
    )


def main() -> None:
    settings, respan = start_respan(
        "crewai-lite-agent",
        metadata={"example": "crewai-lite-agent"},
    )
    try:
        from crewai.lite_agent import LiteAgent

        agent = LiteAgent(
            role="LiteAgent Smoke Tester",
            goal="Return concise answers for direct agent execution.",
            backstory="You test the direct LiteAgent API without building a Crew.",
            llm=settings.model,
            verbose=True,
        )

        sync_output = agent.kickoff(
            "In one sentence, explain what a LiteAgent does in CrewAI."
        )
        async_output = asyncio.run(run_async_lite_agent(agent))

        print_raw_result("CrewAI LiteAgent kickoff result", sync_output)
        print_raw_result("CrewAI LiteAgent kickoff_async result", async_output)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
