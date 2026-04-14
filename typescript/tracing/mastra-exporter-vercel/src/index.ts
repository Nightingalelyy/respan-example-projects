/**
 * Mastra + @respan/exporter-vercel example.
 *
 * Uses @mastra/otel-bridge to produce native OTel spans from Mastra
 * operations, which are then exported to Respan via @respan/exporter-vercel.
 *
 * Run: npx tsx --import ./src/instrumentation.ts src/index.ts
 */
import { provider } from "./instrumentation.js";

const RESPAN_API_KEY =
  process.env.RESPAN_GATEWAY_API_KEY || process.env.RESPAN_API_KEY || "";
const RESPAN_BASE_URL = (
  process.env.RESPAN_GATEWAY_BASE_URL ||
  process.env.RESPAN_BASE_URL ||
  "https://api.respan.ai/api"
).replace(/\/$/, "");

import { Mastra } from "@mastra/core";
import { Observability } from "@mastra/observability";
import { OtelBridge } from "@mastra/otel-bridge";
import { Agent } from "@mastra/core/agent";
import { createTool } from "@mastra/core/tools";
import { createOpenAI } from "@ai-sdk/openai";
import { z } from "zod";

const openai = createOpenAI({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  compatibility: "compatible",
});

const getCurrentTime = createTool({
  id: "get-current-time",
  description: "Get the current date and time",
  inputSchema: z.object({}),
  outputSchema: z.object({
    time: z.string(),
    timezone: z.string(),
  }),
  execute: async () => ({
    time: new Date().toISOString(),
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  }),
});

const haikuAgent = new Agent({
  name: "Haiku Agent",
  instructions:
    "You are a haiku poet. When asked to write a haiku, first check the current time for inspiration, then write a haiku. Output ONLY the haiku.",
  model: openai("gpt-4o-mini"),
  tools: { getCurrentTime },
});

const mastra = new Mastra({
  agents: { haikuAgent },
  observability: new Observability({
    configs: {
      default: {
        serviceName: "mastra-exporter-vercel-example",
        bridge: new OtelBridge(),
      },
    },
  }),
});

async function main() {
  console.log("=".repeat(60));
  console.log("Mastra + @respan/exporter-vercel Example");
  console.log("=".repeat(60));

  if (!RESPAN_API_KEY) {
    console.log("Skipping: RESPAN_API_KEY not set.");
    return;
  }

  const agent = mastra.getAgent("haikuAgent");

  const result = await agent.generateLegacy(
    "Write a haiku about recursion in programming."
  );

  console.log(result.text);

  await provider.forceFlush();
  await new Promise((r) => setTimeout(r, 3000));
  console.log("\nTelemetry flushed.");
}

main().catch(console.error);
