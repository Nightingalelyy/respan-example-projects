/**
 * Tool Use via Gateway — Run agent with tools, routed through Respan gateway.
 *
 * Demonstrates tool calls (Read, Glob, Grep) going through the gateway
 * with a single RESPAN_API_KEY for both LLM and tracing.
 *
 * Run:
 *   npx tsx tool_use_gateway.ts
 */

import "dotenv/config";
import { query } from "@anthropic-ai/claude-agent-sdk";
import { RespanAnthropicAgentsExporter } from "@respan/exporter-anthropic-agents";

const API_KEY = process.env.RESPAN_API_KEY;
const BASE_URL = (
  process.env.RESPAN_BASE_URL || "https://api.respan.ai/api"
).replace(/\/+$/, "");

if (!API_KEY) {
  console.error("ERROR: Set RESPAN_API_KEY");
  process.exit(1);
}

const exporter = new RespanAnthropicAgentsExporter({
  apiKey: API_KEY,
});

const gatewayUrl = `${BASE_URL}/anthropic`;

let sessionId: string | undefined;

for await (const message of query({
  prompt: "List the TypeScript files in the current directory. Just show filenames.",
  options: exporter.withOptions({
    permissionMode: "bypassPermissions",
    maxTurns: 3,
    allowedTools: ["Read", "Glob", "Grep"],
    env: {
      ANTHROPIC_BASE_URL: gatewayUrl,
      ANTHROPIC_AUTH_TOKEN: API_KEY,
      ANTHROPIC_API_KEY: API_KEY,
    },
  }),
})) {
  if (message.type === "system") sessionId = message.data?.session_id;
  await exporter.trackMessage({ message, sessionId });
  console.log(`  ${message.type}`);
}

console.log(`\nSession: ${sessionId}`);
console.log("Check Respan traces to see tool spans (Read, Glob, etc.)");
