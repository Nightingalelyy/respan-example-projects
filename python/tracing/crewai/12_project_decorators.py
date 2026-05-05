#!/usr/bin/env python3
"""CrewAI project decorators: CrewBase, agent, task, crew, before/after kickoff."""

from __future__ import annotations

from typing import Any

from common import print_raw_result, start_respan

def build_decorated_tracing_crew_class():
    from crewai import Agent, Crew, Process, Task
    from crewai.project import (
        CrewBase,
        after_kickoff,
        agent as agent_decorator,
        before_kickoff,
        crew as crew_decorator,
        task as task_decorator,
    )

    @CrewBase
    class DecoratedTracingCrew:
        agents_config = None
        tasks_config = None

        @before_kickoff
        def add_default_inputs(self, inputs: dict[str, Any] | None) -> dict[str, Any]:
            inputs = dict(inputs or {})
            inputs.setdefault("topic", "CrewAI project decorators")
            return inputs

        @after_kickoff
        def annotate_output(self, output: Any) -> Any:
            print("\nDecorated crew after_kickoff received output.")
            return output

        @agent_decorator
        def writer(self) -> Agent:
            return Agent(
                role="Decorated Crew Writer",
                goal="Explain the project decorator API in short form.",
                backstory="You build CrewAI projects with decorator-based structure.",
                llm=self.model,
                verbose=True,
            )

        @task_decorator
        def explanation(self) -> Task:
            return Task(
                description="Explain {topic} in two short bullets.",
                expected_output="Two bullets.",
                agent=self.writer(),
            )

        @crew_decorator
        def crew(self) -> Crew:
            return Crew(
                agents=self.agents,
                tasks=self.tasks,
                process=Process.sequential,
                verbose=True,
            )

        def __init__(self, model: str) -> None:
            self.model = model

    return DecoratedTracingCrew


def main() -> None:
    settings, respan = start_respan(
        "crewai-project-decorators",
        metadata={"example": "crewai-project-decorators"},
    )
    try:
        DecoratedTracingCrew = build_decorated_tracing_crew_class()
        result = DecoratedTracingCrew(settings.model).crew().kickoff(inputs={})
        print_raw_result("CrewAI project decorators result", result)
    finally:
        respan.flush()
        respan.shutdown()


if __name__ == "__main__":
    main()
