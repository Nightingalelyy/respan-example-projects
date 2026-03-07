import json
import os
import sys

from dotenv import load_dotenv
from openinference.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from pydantic import BaseModel, Field
from crewai import Agent, Crew, Task
from crewai.tools import tool
from crewai.tools.structured_tool import CrewStructuredTool
from respan_exporter_crewai.instrumentor import RespanCrewAIInstrumentor
from respan_exporter_crewai.utils import normalize_respan_base_url_for_gateway

# Load environment variables from the root .env file
load_dotenv(os.path.join(os.path.dirname(__file__), "../../../.env"))

# CrewAI 1.10 runs tools via CrewStructuredTool.invoke(), not BaseTool.run(), so
# OpenInference's BaseTool.run patch never fires. We patch invoke/ainvoke so tool
# runs show up as spans (with crewai.* and openinference.span.kind for exporter).
_TOOL_INVOKE_ORIGINAL = CrewStructuredTool.invoke
_TOOL_AINVOKE_ORIGINAL = CrewStructuredTool.ainvoke


def _tool_span_attributes(self: CrewStructuredTool, input: str | dict) -> dict[str, object]:
    """Attributes so Respan exporter recognizes this as a tool span (crewai + tool.name)."""
    inp = json.dumps(input) if not isinstance(input, str) else input
    return {
        "crewai.tool.name": self.name,
        "tool.name": self.name,
        "tool_name": self.name,
        "openinference.span.kind": "TOOL",
        "input.value": inp,
    }


def _invoke_with_span(self: CrewStructuredTool, input: str | dict, config: dict | None = None, **kwargs: object) -> object:
    print(f"[DEBUG] _invoke_with_span called for tool={getattr(self, 'name', '?')}", file=sys.stderr)
    tracer = trace.get_tracer("openinference.instrumentation.crewai", "0.1.21")
    current = trace.get_current_span()
    if not current.is_recording():
        return _TOOL_INVOKE_ORIGINAL(self, input=input, config=config, **kwargs)
    with tracer.start_as_current_span(
        f"{self.name}.invoke",
        attributes=_tool_span_attributes(self, input),
    ) as span:
        result = _TOOL_INVOKE_ORIGINAL(self, input=input, config=config, **kwargs)
        span.set_attribute("output.value", json.dumps(result) if not isinstance(result, (str, int, float)) else str(result))
        return result


async def _ainvoke_with_span(self: CrewStructuredTool, input: str | dict, config: dict | None = None, **kwargs: object) -> object:
    print(f"[DEBUG] _ainvoke_with_span called for tool={getattr(self, 'name', '?')}", file=sys.stderr)
    tracer = trace.get_tracer("openinference.instrumentation.crewai", "0.1.21")
    current = trace.get_current_span()
    if not current.is_recording():
        return await _TOOL_AINVOKE_ORIGINAL(self, input=input, config=config, **kwargs)
    with tracer.start_as_current_span(
        f"{self.name}.ainvoke",
        attributes=_tool_span_attributes(self, input),
    ) as span:
        result = await _TOOL_AINVOKE_ORIGINAL(self, input=input, config=config, **kwargs)
        span.set_attribute("output.value", json.dumps(result) if not isinstance(result, (str, int, float)) else str(result))
        return result


def _patch_crew_structured_tool_for_tracing() -> None:
    CrewStructuredTool.invoke = _invoke_with_span  # type: ignore[method-assign]
    CrewStructuredTool.ainvoke = _ainvoke_with_span  # type: ignore[method-assign]


# Apply patch at import so it is in place before CrewAI uses tools (avoids stale references).
_patch_crew_structured_tool_for_tracing()

# Define structured output model
class ToolAnalysisResult(BaseModel):
    tool_used: str = Field(description="Name of the tool that was used")
    answer: int = Field(description="The calculated numeric answer")
    explanation: str = Field(description="Explanation of the answer")

@tool("Multiplier Tool")
def multiplier_tool(number: int, factor: int) -> int:
    """Multiplies a number by a given factor."""
    return number * factor

def main() -> None:
    """
    Additional: Tool Use and Structured Output
    
    Demonstrates CrewAI integration with custom tools and structured output formatting.
    All tool inputs, outputs, and structured LLM responses will be traced in Respan.
    """
    api_key = os.getenv("RESPAN_API_KEY")
    if not api_key:
        print("Please set RESPAN_API_KEY environment variable.")
        sys.exit(1)

    base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
    os.environ["OPENAI_BASE_URL"] = normalize_respan_base_url_for_gateway(base_url)
    os.environ["OPENAI_API_KEY"] = api_key

    # Set global TracerProvider with a span processor so CrewAI spans are exported to Respan
    tracer_provider = trace.get_tracer_provider()
    if not isinstance(tracer_provider, TracerProvider):
        tracer_provider = TracerProvider()
        trace.set_tracer_provider(tracer_provider)
    tracer_provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    RespanCrewAIInstrumentor().instrument(api_key=api_key)
    CrewAIInstrumentor().instrument()

    # 1. Define agent with tools
    math_agent = Agent(
        role="Mathematician",
        goal="Solve math problems using the provided tools.",
        backstory="A highly accurate math bot.",
        tools=[multiplier_tool],
        verbose=True
    )

    # 2. Define task with structured output
    math_task = Task(
        description="Multiply 15 by 7 using your tools.",
        expected_output="A structured math result.",
        agent=math_agent,
        output_pydantic=ToolAnalysisResult
    )

    crew = Crew(
        agents=[math_agent],
        tasks=[math_task],
        verbose=True
    )

    print("Running Tool Use & Structured Output Crew...")
    result = crew.kickoff()

    # Force flush so spans are exported before process exits
    tracer_provider = trace.get_tracer_provider()
    if isinstance(tracer_provider, TracerProvider):
        tracer_provider.force_flush()

    print("\nStructured Output Result:")
    print(result)

if __name__ == "__main__":
    main()
