/**
 * Together AI — Chat completion with Respan tracing via Traceloop.
 *
 * The together-ai SDK uses an OpenAI-compatible API (chat.completions.create),
 * so it can be pointed directly at the Respan gateway without a proxy.
 *
 * The @traceloop/instrumentation-together patches
 * Chat.Completions.prototype.create to create Traceloop-format OTel spans.
 */

import "dotenv/config";
import { trace } from "@opentelemetry/api";
import { TogetherInstrumentation } from "@traceloop/instrumentation-together";
import Together from "together-ai";
import { Respan } from "@respan/respan";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api"
).replace(/\/+$/, "");

// ── 1. Initialize Respan tracing ──────────────────────────────────────
const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
});
await respan.initialize();

// ── 2. Manually instrument together-ai ────────────────────────────────
const instrumentation = new TogetherInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument(Together);

// ── 3. Create Together client pointing at Respan gateway ──────────────
const together = new Together({
  apiKey: RESPAN_API_KEY,
  baseURL: `${RESPAN_BASE_URL}/chat/completions`.replace("/chat/completions", ""),
});

const result = await together.chat.completions.create({
  model: "gpt-4o-mini",
  messages: [
    { role: "user", content: "Write a haiku about recursion in programming." },
  ],
  temperature: 0,
  max_tokens: 256,
});

console.log(result.choices[0]?.message?.content);

// ── 4. Flush ──────────────────────────────────────────────────────────
await respan.flush();
