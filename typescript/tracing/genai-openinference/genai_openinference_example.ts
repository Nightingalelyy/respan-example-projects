/**
 * OpenInference GenAI — Convert gen_ai.* OTel attributes to OpenInference format.
 *
 * @arizeai/openinference-genai is a utility that converts standard gen_ai.*
 * OpenTelemetry semantic convention attributes into OpenInference attributes
 * (span kind, messages, model, tokens, etc.).
 *
 * This example:
 * 1. Creates a custom SpanProcessor that calls the conversion function on each span
 * 2. Makes a real LLM call via the OpenAI SDK through the Respan gateway
 * 3. Wraps the call in a manually-created span with gen_ai.* attributes
 * 4. The processor converts gen_ai.* → OpenInference and exports to Respan
 */

import "dotenv/config";
import OpenAI from "openai";
import { trace, context, SpanStatusCode } from "@opentelemetry/api";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import {
  SimpleSpanProcessor,
  type ReadableSpan,
  type Span,
} from "@opentelemetry/sdk-trace-base";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { Resource } from "@opentelemetry/resources";
import { convertGenAISpanAttributesToOpenInferenceSpanAttributes } from "@arizeai/openinference-genai";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api"
).replace(/\/+$/, "");

// ── 1. Custom SpanProcessor that converts gen_ai.* → OpenInference ────
class GenAIOpenInferenceSpanProcessor extends SimpleSpanProcessor {
  onEnd(span: ReadableSpan): void {
    const newAttrs = convertGenAISpanAttributesToOpenInferenceSpanAttributes(
      span.attributes
    );
    if (newAttrs) {
      for (const [key, value] of Object.entries(newAttrs)) {
        if (value !== undefined) {
          (span as any).attributes[key] = value;
        }
      }
    }
    super.onEnd(span);
  }
}

// ── 2. Set up OTel TracerProvider → Respan OTLP ──────────────────────
const exporter = new OTLPTraceExporter({
  url: `${RESPAN_BASE_URL}/v2/traces`,
  headers: { Authorization: `Bearer ${RESPAN_API_KEY}` },
});

const provider = new NodeTracerProvider({
  resource: new Resource({ "service.name": "genai-openinference-example" }),
  spanProcessors: [new GenAIOpenInferenceSpanProcessor(exporter)],
});
provider.register();

const tracer = trace.getTracer("genai-openinference-example");

// ── 3. OpenAI client pointing at Respan gateway ──────────────────────
const openai = new OpenAI({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
});

// ── 4. Make LLM call wrapped in a span with gen_ai.* attributes ──────
const prompt = "Write a haiku about recursion in programming.";

const result = await tracer.startActiveSpan("chat", async (span) => {
  // Set gen_ai.* attributes (OTel GenAI semantic conventions)
  span.setAttribute("gen_ai.system", "openai");
  span.setAttribute("gen_ai.request.model", "gpt-4o-mini");
  span.setAttribute("gen_ai.request.temperature", 0);
  span.setAttribute("gen_ai.request.max_tokens", 256);
  span.setAttribute(
    "gen_ai.input.messages",
    JSON.stringify([
      { role: "user", parts: [{ type: "text", content: prompt }] },
    ])
  );

  try {
    const response = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      temperature: 0,
      max_tokens: 256,
    });

    const choice = response.choices[0];
    const text = choice?.message?.content ?? "";

    span.setAttribute("gen_ai.response.model", response.model);
    span.setAttribute("gen_ai.response.id", response.id);
    span.setAttribute(
      "gen_ai.response.finish_reasons",
      choice?.finish_reason ?? "stop"
    );
    span.setAttribute(
      "gen_ai.usage.input_tokens",
      response.usage?.prompt_tokens ?? 0
    );
    span.setAttribute(
      "gen_ai.usage.output_tokens",
      response.usage?.completion_tokens ?? 0
    );
    span.setAttribute(
      "gen_ai.output.messages",
      JSON.stringify([
        {
          role: "assistant",
          parts: [{ type: "text", content: text }],
        },
      ])
    );

    span.setStatus({ code: SpanStatusCode.OK });
    span.end();
    return text;
  } catch (err: any) {
    span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
    span.end();
    throw err;
  }
});

console.log(result);

// ── 5. Flush and shutdown ─────────────────────────────────────────────
await provider.forceFlush();
await provider.shutdown();
