/** LlamaIndex — Chat completion with Respan tracing via Traceloop. */

import "dotenv/config";
import { trace } from "@opentelemetry/api";
import * as llamaindex from "llamaindex";
import * as llamaindexOpenAI from "@llamaindex/openai";
import { OpenAI } from "@llamaindex/openai";
import { LlamaIndexInstrumentation } from "@traceloop/instrumentation-llamaindex";
import { Respan } from "@respan/respan";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY;
const RESPAN_BASE_URL = (process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api").replace(/\/+$/, "");

const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
});
await respan.initialize();

const instrumentation = new LlamaIndexInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument({ ...llamaindex, ...llamaindexOpenAI });

const llm = new OpenAI({
  model: "gpt-4o-mini",
  temperature: 0,
  apiKey: RESPAN_API_KEY,
  additionalSessionOptions: { baseURL: RESPAN_BASE_URL },
});

const response = await llm.chat({
  messages: [{ role: "user", content: "Write a haiku about recursion in programming." }],
});

console.log(response.message.content);

await respan.flush();
