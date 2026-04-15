import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import type { Options } from "@anthropic-ai/claude-agent-sdk";
import { ClaudeAgentSDKInstrumentor } from "@respan/instrumentation-claude-agent-sdk";
import { Respan } from "@respan/respan";
import dotenv from "dotenv";

const __filename = fileURLToPath(import.meta.url);

export const EXAMPLE_DIR = path.dirname(__filename);
export const EXAMPLE_REPO_ROOT = path.resolve(EXAMPLE_DIR, "../../..");
export const ROOT_ENV_PATH = path.join(EXAMPLE_REPO_ROOT, ".env");

if (fs.existsSync(ROOT_ENV_PATH)) {
  dotenv.config({ path: ROOT_ENV_PATH, override: true });
} else {
  dotenv.config({ override: true });
}

export const LOADED_ENV_PATH = fs.existsSync(ROOT_ENV_PATH)
  ? ROOT_ENV_PATH
  : "dotenv default lookup";

export const RESPAN_API_KEY =
  process.env.RESPAN_GATEWAY_API_KEY || process.env.RESPAN_API_KEY;
export const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL || "https://api.respan.ai/api"
).replace(/\/+$/, "");
export const CLAUDE_AGENT_MODEL = process.env.CLAUDE_AGENT_MODEL || "sonnet";
export const ANTHROPIC_GATEWAY_URL = `${RESPAN_BASE_URL}/anthropic`;

if (!RESPAN_API_KEY) {
  throw new Error(
    "RESPAN_GATEWAY_API_KEY or RESPAN_API_KEY must be set in the repo-root .env.",
  );
}

process.env.ANTHROPIC_API_KEY ||= RESPAN_API_KEY;
process.env.ANTHROPIC_AUTH_TOKEN ||= RESPAN_API_KEY;
process.env.ANTHROPIC_BASE_URL ||= ANTHROPIC_GATEWAY_URL;

export function buildClaudeEnv(): NodeJS.ProcessEnv {
  return {
    ...process.env,
    ANTHROPIC_API_KEY: RESPAN_API_KEY,
    ANTHROPIC_AUTH_TOKEN: RESPAN_API_KEY,
    ANTHROPIC_BASE_URL: ANTHROPIC_GATEWAY_URL,
  };
}

export function buildBaseQueryOptions(overrides: Partial<Options> = {}): Options {
  return {
    model: CLAUDE_AGENT_MODEL,
    cwd: EXAMPLE_DIR,
    permissionMode: "bypassPermissions",
    allowDangerouslySkipPermissions: true,
    env: buildClaudeEnv(),
    ...overrides,
  };
}

export function createRespan(options: {
  appName: string;
  agentName?: string;
  sdkModule: Record<string, unknown>;
}): Respan {
  return new Respan({
    apiKey: RESPAN_API_KEY,
    baseURL: RESPAN_BASE_URL,
    appName: options.appName,
    instrumentations: [
      new ClaudeAgentSDKInstrumentor({
        sdkModule: options.sdkModule,
        agentName: options.agentName || options.appName,
      }),
    ],
  });
}

export function printCommonSummary(options: {
  title: string;
  customerIdentifier: string;
  exampleName: string;
}): void {
  console.log(`\n=== ${options.title} ===`);
  console.log(`Base URL:            ${RESPAN_BASE_URL}`);
  console.log(`Anthropic URL:       ${ANTHROPIC_GATEWAY_URL}`);
  console.log(`Claude model:        ${CLAUDE_AGENT_MODEL}`);
  console.log(`Loaded .env:         ${LOADED_ENV_PATH}`);
  console.log();
  console.log("Check traces in Respan with:");
  console.log(`  customer_identifier = ${options.customerIdentifier}`);
  console.log(`  metadata.example_name = ${options.exampleName}`);
}
