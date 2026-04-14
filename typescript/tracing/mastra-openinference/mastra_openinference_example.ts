/** Mastra — Agent chat completion with Respan tracing via OpenInference.
 *
 * Sets up OTel tracing with OpenInferenceOTLPTraceExporter to export
 * Mastra/AI SDK spans to Respan's OTLP endpoint.
 */

import "dotenv/config";
import { NodeTracerProvider } from "@opentelemetry/sdk-trace-node";
import { BatchSpanProcessor, SimpleSpanProcessor, ConsoleSpanExporter } from "@opentelemetry/sdk-trace-base";
import { OpenInferenceOTLPTraceExporter } from "@arizeai/openinference-mastra";
import { Agent } from "@mastra/core/agent";
import { createOpenAI } from "@ai-sdk/openai";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api").replace(/\/+$/, "");

const exporter = new OpenInferenceOTLPTraceExporter({
  url: `${RESPAN_BASE_URL.replace(/\/api$/, "")}/api/v2/traces`,
  headers: {
    Authorization: `Bearer ${RESPAN_API_KEY}`,
  },
});

const provider = new NodeTracerProvider({
  spanProcessors: [
    new SimpleSpanProcessor(new ConsoleSpanExporter()),
    new BatchSpanProcessor(exporter),
  ],
});
provider.register();

const openai = createOpenAI({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
});

const agent = new Agent({
  id: "haiku-agent",
  name: "Haiku Agent",
  instructions: "You are a helpful assistant that writes haikus. Respond only with a haiku.",
  model: openai("gpt-4o-mini"),
});

const result = await agent.generate("Write a haiku about recursion in programming.", {
  experimental_telemetry: { isEnabled: true },
});

console.log("Agent response:", result.text);

await provider.forceFlush();
await provider.shutdown();
console.log("Traces exported.");
