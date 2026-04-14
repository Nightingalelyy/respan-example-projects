/**
 * Vercel AI SDK — generateText with Respan tracing via OpenInference.
 *
 * The Vercel AI SDK has built-in OpenTelemetry telemetry support via the
 * `experimental_telemetry` option. The @arizeai/openinference-vercel package
 * provides a SpanProcessor that transforms these Vercel AI SDK spans into
 * OpenInference-format attributes (span kind, messages, model, tokens, etc.).
 *
 * Since this is a SpanProcessor (not an Instrumentation), we set up the
 * OTel TracerProvider directly with the OpenInferenceSimpleSpanProcessor
 * and export traces to Respan's OTLP endpoint.
 *
 * The @ai-sdk/openai provider is pointed at the Respan gateway so
 * the LLM call is routed through Respan.
 */

import "dotenv/config";
import { generateText } from "ai";
import { createOpenAI } from "@ai-sdk/openai";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-proto";
import { Resource } from "@opentelemetry/resources";
import { OpenInferenceSimpleSpanProcessor } from "@arizeai/openinference-vercel";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api"
).replace(/\/+$/, "");

// ── 1. Set up OTel with OpenInference processor → Respan OTLP ────────
const exporter = new OTLPTraceExporter({
  url: `${RESPAN_BASE_URL}/v2/traces`,
  headers: {
    Authorization: `Bearer ${RESPAN_API_KEY}`,
  },
});

const provider = new NodeTracerProvider({
  resource: new Resource({ "service.name": "vercel-ai-example" }),
  spanProcessors: [
    new OpenInferenceSimpleSpanProcessor({ exporter }),
  ],
});
provider.register();

// ── 2. Create OpenAI provider pointing at Respan gateway ─────────────
const openai = createOpenAI({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  compatibility: "compatible",
});

// ── 3. Generate text with telemetry enabled ───────────────────────────
const result = await generateText({
  model: openai("gpt-4o-mini"),
  prompt: "Write a haiku about recursion in programming.",
  experimental_telemetry: { isEnabled: true },
});

console.log(result.text);
console.log(`\nTokens: ${result.usage.promptTokens} prompt, ${result.usage.completionTokens} completion`);

// ── 4. Flush and shutdown ─────────────────────────────────────────────
await provider.forceFlush();
await provider.shutdown();
