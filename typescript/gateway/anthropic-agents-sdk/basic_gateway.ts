/**
 * Basic Gateway — Route Claude Agent SDK calls through Respan gateway.
 *
 * Only needs RESPAN_API_KEY — no Anthropic key required. The gateway proxies
 * Claude API calls, so a single key handles both the LLM call and trace export.
 *
 * Setup:
 *   npm install
 *
 * Environment:
 *   RESPAN_API_KEY=your_key    # only key needed
 *
 * Run:
 *   npx tsx basic_gateway.ts
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

// The Anthropic SDK appends /v1/messages to ANTHROPIC_BASE_URL,
// so point it at the gateway's /anthropic passthrough path.
// Final URL: {BASE_URL}/anthropic/v1/messages
const gatewayUrl = `${BASE_URL}/anthropic`;

let sessionId: string | undefined;

for await (const message of query({
  prompt: "Reply with exactly: gateway_ok",
  options: exporter.withOptions({
    permissionMode: "bypassPermissions",
    maxTurns: 1,
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
console.log("View trace at: https://platform.respan.ai/platform/traces");
