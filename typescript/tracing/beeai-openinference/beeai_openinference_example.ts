/** BeeAI — ReAct agent with Respan tracing via OpenInference. */

import "dotenv/config";
import { trace } from "@opentelemetry/api";
import { BeeAIInstrumentation } from "@arizeai/openinference-instrumentation-beeai";
import { Respan } from "@respan/respan";
import { OpenInferenceInstrumentor } from "@respan/instrumentation-openinference";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY;
const RESPAN_BASE_URL = (process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api").replace(/\/+$/, "");

process.env.OPENAI_API_KEY = RESPAN_API_KEY;
process.env.OPENAI_API_ENDPOINT = RESPAN_BASE_URL;

const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  instrumentations: [
    new OpenInferenceInstrumentor(BeeAIInstrumentation),
  ],
});
await respan.initialize();

// Import beeai-framework AFTER instrumentation is initialized
const beeaiFramework = await import("beeai-framework");
const beeAIInst = new BeeAIInstrumentation();
beeAIInst.setTracerProvider(trace.getTracerProvider());
beeAIInst.manuallyInstrument(beeaiFramework);

const { ChatModel } = await import("beeai-framework/backend/chat");
const { ReActAgent } = await import("beeai-framework/agents/react/agent");
const { TokenMemory } = await import("beeai-framework/memory/tokenMemory");

const llm = await ChatModel.fromName("openai:gpt-4o-mini" as any);
const agent = new ReActAgent({ llm, memory: new TokenMemory(), tools: [] });

const response = await agent.run({ prompt: "Write a haiku about recursion in programming." });

console.log(response.result.text);

await respan.flush();
