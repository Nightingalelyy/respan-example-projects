#!/usr/bin/env python3
"""CrewAI hierarchical process with planning and streaming output."""

from __future__ import annotations

from common import start_respan


def main() -> None:
    settings, respan = start_respan(
        "crewai-hierarchical-planning-streaming",
        metadata={"example": "crewai-hierarchical-planning-streaming"},
    )
    try:
        from crewai import Agent, Crew, Process, Task

        researcher = Agent(
            role="Observability Researcher",
            goal="Find practical tracing checks for CrewAI applications.",
            backstory="You audit agent workflows for production readiness.",
            llm=settings.model,
            verbose=True,
        )
        writer = Agent(
            role="Runbook Writer",
            goal="Turn research into concise operational guidance.",
            backstory="You write compact runbooks for on-call engineers.",
            llm=settings.model,
            verbose=True,
        )

        research_task = Task(
            description="List two tracing checks for a CrewAI production rollout.",
            expected_output="Two bullet points.",
            agent=researcher,
        )
        runbook_task = Task(
            description=(
                "Use the research context to write a three-step rollout checklist "
                "for CrewAI tracing."
            ),
            expected_output="A three-step checklist.",
            agent=writer,
            context=[research_task],
        )

        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, runbook_task],
            process=Process.hierarchical,
            manager_llm=settings.model,
            planning=True,
            planning_llm=settings.model,
            stream=True,
            verbose=True,
        )

        streaming = crew.kickoff()
        print("\n=== CrewAI hierarchical streaming chunks ===")
        for chunk in streaming:
            print(chunk.content, end="", flush=True)
        print("\n\n=== CrewAI hierarchical final result ===")
        print(streaming.result.raw)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
