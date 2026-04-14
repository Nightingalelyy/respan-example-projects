#!/usr/bin/env python3
"""
Pipecat + OpenInference example for Respan tracing.

Uses openinference-instrumentation-pipecat to auto-instrument Pipecat pipelines
and exports spans to Respan via the respan-instrumentation-openinference wrapper.

Pipecat is a framework for building real-time voice and multimodal AI pipelines.
This example creates a simple text-only pipeline (no audio) with an OpenAI LLM
service, demonstrating the instrumentation's ability to trace LLM frame flow.
"""
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")

from openinference.instrumentation.pipecat import PipecatInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry

telemetry = RespanTelemetry(
    app_name="pipecat-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

pipecat_oi = OpenInferenceInstrumentor(PipecatInstrumentor)
pipecat_oi.activate()

import warnings

from pipecat.frames.frames import LLMContextFrame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.processors.aggregators.llm_response import LLMFullResponseAggregator
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.openai.llm import OpenAILLMService

warnings.filterwarnings("ignore", category=DeprecationWarning)


class TextCollector(FrameProcessor):
    """Collects TextFrame output from the pipeline."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.collected_text: list[str] = []

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame):
            self.collected_text.append(frame.text)
        await self.push_frame(frame, direction)


async def main() -> None:
    print("=" * 60)
    print("Pipecat OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    llm = OpenAILLMService(
        model="gpt-4o-mini",
        api_key=RESPAN_API_KEY,
        base_url=RESPAN_BASE_URL,
    )

    aggregator = LLMFullResponseAggregator()
    collector = TextCollector()

    pipeline = Pipeline([llm, aggregator, collector])

    task = PipelineTask(
        pipeline,
        conversation_id="pipecat-example-001",
        idle_timeout_secs=3,
        cancel_on_idle_timeout=True,
    )

    from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext

    context = OpenAILLMContext.from_messages([
        {"role": "user", "content": "Write a haiku about recursion in programming. Output ONLY the haiku."},
    ])
    await task.queue_frame(LLMContextFrame(context))

    runner = PipelineRunner(handle_sigint=False)
    await runner.run(task)

    result = " ".join(collector.collected_text)
    print(result)

    telemetry.flush()
    pipecat_oi.deactivate()


if __name__ == "__main__":
    asyncio.run(main())
