#!/usr/bin/env python3
"""CrewAI ConditionalTask example for branching task execution."""

from __future__ import annotations

from typing import Any

from common import print_raw_result, start_respan


def needs_followup(output: Any) -> bool:
    raw = getattr(output, "raw", "")
    return "yes" in raw.lower()


def main() -> None:
    settings, respan = start_respan(
        "crewai-conditional-task",
        metadata={"example": "crewai-conditional-task"},
    )
    try:
        from crewai import Agent, Crew, Task
        from crewai.tasks.conditional_task import ConditionalTask

        analyst = Agent(
            role="Risk Analyst",
            goal="Classify whether a follow-up task should run.",
            backstory="You return clear yes/no risk decisions.",
            llm=settings.model,
            verbose=True,
        )
        responder = Agent(
            role="Follow-up Responder",
            goal="Write follow-up action items only when needed.",
            backstory="You produce concise incident follow-up plans.",
            llm=settings.model,
            verbose=True,
        )

        classify = Task(
            description=(
                "A checkout incident affects payment authorization for all users. "
                "Start your answer with YES if follow-up is needed."
            ),
            expected_output="A yes/no decision with one reason.",
            agent=analyst,
        )
        followup = ConditionalTask(
            condition=needs_followup,
            description="Write two follow-up actions based on the risk decision.",
            expected_output="Two numbered follow-up actions.",
            agent=responder,
            context=[classify],
        )

        result = Crew(
            agents=[analyst, responder],
            tasks=[classify, followup],
            verbose=True,
        ).kickoff()

        print_raw_result("CrewAI conditional task result", result)
        print("\n=== Task outputs ===")
        for task_output in result.tasks_output:
            print(f"- {task_output.description}: {task_output.raw}")
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
