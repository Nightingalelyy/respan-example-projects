/**
 * Wrapped Query — the simplest integration pattern.
 *
 * Uses exporter.query() which handles hooks + tracking automatically.
 * One line to instrument, zero boilerplate.
 *
 * Setup:
 *   npm install (or yarn install)
 *
 * Run:
 *   npx tsx wrapped_query_test.ts
 */

import "dotenv/config";
import { RespanAnthropicAgentsExporter } from "@respan/exporter-anthropic-agents";
import { queryForResult } from "./_sdk_runtime";

const API_KEY = process.env.RESPAN_API_KEY;
const BASE_URL = process.env.RESPAN_BASE_URL;

const exporter = new RespanAnthropicAgentsExporter({
  apiKey: API_KEY ?? undefined,
  endpoint: BASE_URL ? `${BASE_URL.replace(/\/+$/, "")}/v1/traces/ingest` : undefined,
});

async function main(): Promise<void> {
  console.log("Running wrapped query — exporter handles everything...\n");

  if (!API_KEY) {
    throw new Error("Set RESPAN_API_KEY to run this example.");
  }

  const { messageTypes, result } = await queryForResult({
    prompt: "Name three primary colors. One word each, comma separated.",
    options: exporter.withOptions({
      permissionMode: "bypassPermissions",
      maxTurns: 1,
    } as any),
    onMessage: async (message, context) => {
      await exporter.trackMessage({ message, sessionId: context.sessionId });
      console.log(`  ${String(message.type ?? "unknown")}`);
    },
  });

  console.log(`\nMessage flow: ${messageTypes.join(" -> ")}`);
  console.log(
    `Result: subtype=${String(result.subtype)}, turns=${String(result.num_turns)}`,
  );
  console.log("All traces exported automatically via exporter.query()");
}

main().catch(console.error);
