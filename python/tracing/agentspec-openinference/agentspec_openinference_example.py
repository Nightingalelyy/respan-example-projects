#!/usr/bin/env python3
"""
AgentSpec + OpenInference example for Respan tracing.

Uses openinference-instrumentation-agentspec to auto-instrument AgentSpec
and exports spans to Respan via the respan-instrumentation-openinference wrapper.

NOTE: The AgentSpec instrumentor has its own tracing runtime
(pyagentspec.tracing.trace.Trace) that creates spans independently of the
OTel context.  It wraps each OTel SpanProcessor in an
OpenInferenceSpanProcessor, converting AgentSpec trace events to OI-formatted
OTel spans.  Because of this parallel pipeline, we must:

1. NOT use the OpenInferenceInstrumentor wrapper (it inserts the translator
   as a separate processor, which the AgentSpec instrumentor wraps
   independently — the translator then processes a different span copy).
2. NOT use @workflow/@task decorators (their trace context is separate from
   the AgentSpec Trace object's trace context, causing trace splitting).
3. Instead, create a *combined* processor that runs the OI→Traceloop
   translator inline before passing spans to the export chain.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanProcessor
from openinference.instrumentation.agentspec import AgentSpecInstrumentor
from pyagentspec.adapters.langgraph import AgentSpecLoader
from pyagentspec.agent import Agent
from pyagentspec.llms import OpenAiConfig
from respan_instrumentation_openinference._translator import OpenInferenceTranslator
from respan_tracing import RespanTelemetry

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")

os.environ["OPENAI_API_KEY"] = RESPAN_API_KEY
os.environ["OPENAI_BASE_URL"] = RESPAN_BASE_URL

telemetry = RespanTelemetry(
    app_name="agentspec-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)


class TranslatingProcessor(SpanProcessor):
    """Runs the OI→Traceloop translator inline, then forwards to the
    original processor.  This ensures OI attributes are translated
    BEFORE the Respan filtering/export chain sees the span."""

    def __init__(self, translator: OpenInferenceTranslator, inner: SpanProcessor):
        self._translator = translator
        self._inner = inner

    def on_start(self, span, parent_context=None):
        self._inner.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan):
        self._translator.on_end(span)
        self._inner.on_end(span)

    def shutdown(self):
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000):
        return self._inner.force_flush(timeout_millis)


# Replace the TracerProvider's processors with translator-wrapped versions
# so the AgentSpec instrumentor (which wraps each processor individually)
# gets a single processor that translates AND exports in one pass.
tp = trace.get_tracer_provider()
asp = getattr(tp, "_active_span_processor", None)
original_processors = list(getattr(asp, "_span_processors", ()))

translator = OpenInferenceTranslator()
wrapped_processors = tuple(
    TranslatingProcessor(translator, proc) for proc in original_processors
)
asp._span_processors = wrapped_processors

# Now instrument — the AgentSpec instrumentor will wrap our combined
# TranslatingProcessor instances, ensuring OI→Traceloop translation
# happens on the SAME span object that reaches the exporter.
instrumentor = AgentSpecInstrumentor()
instrumentor.instrument(tracer_provider=tp)

agent = Agent(
    name="haiku_assistant",
    description="A helpful assistant that writes haikus.",
    llm_config=OpenAiConfig(
        name="respan-openai",
        model_id="gpt-4o-mini",
        api_key=RESPAN_API_KEY,
    ),
    system_prompt="You are a helpful assistant. Respond only with a haiku.",
)

langgraph_agent = AgentSpecLoader().load_component(agent)


def main() -> None:
    print("=" * 60)
    print("AgentSpec OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = langgraph_agent.invoke(
            input={"messages": [{"role": "user", "content": "Write a haiku about recursion in programming."}]},
        )
        print(result["messages"][-1].content)
    finally:
        telemetry.flush()
        instrumentor.uninstrument()


if __name__ == "__main__":
    main()
