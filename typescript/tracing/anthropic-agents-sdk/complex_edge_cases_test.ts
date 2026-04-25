/**
 * Complex edge cases for the official Anthropic TypeScript SDK routed through
 * the Respan gateway and traced with the local Respan Anthropic instrumentor.
 *
 * This example intentionally exercises the real SDK surfaces documented at:
 * https://platform.claude.com/docs/en/api/sdks/typescript
 *
 * Covered SDK entry points:
 * - `client.messages.create(...)`
 * - `client.messages.create({ ..., stream: true })`
 * - `client.messages.stream(...).on("text").finalMessage()`
 * - Messages API tool use with `tools` + `tool_choice` + `tool_result`
 *
 * Only `RESPAN_API_KEY` is required. Anthropic requests are routed to:
 *   {RESPAN_GATEWAY_BASE_URL|RESPAN_BASE_URL}/anthropic/v1/messages
 *
 * Run:
 *   npx tsx complex_edge_cases_test.ts
 */

import "dotenv/config";
import Anthropic from "@anthropic-ai/sdk";

import { Respan } from "../../../../respan/javascript-sdks/respan/src/index.ts";
import { AnthropicInstrumentor } from "../../../../respan/javascript-sdks/instrumentations/respan-instrumentation-anthropic/src/index.ts";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY;
const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL ||
  process.env.RESPAN_GATEWAY_BASE_URL ||
  "https://api.respan.ai/api"
).replace(/\/+$/, "");
const RESPAN_GATEWAY_BASE_URL = (
  process.env.RESPAN_GATEWAY_BASE_URL ||
  RESPAN_BASE_URL
).replace(/\/+$/, "");
const ANTHROPIC_BASE_URL = (
  process.env.ANTHROPIC_BASE_URL ||
  `${RESPAN_GATEWAY_BASE_URL}/anthropic`
).replace(/\/+$/, "");
const ANTHROPIC_MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-5";

const EXAMPLE_NAME = "anthropic_sdk_complex_edge_cases";
const CUSTOMER_IDENTIFIER = "anthropic-sdk-complex-edge-cases-v1";

if (!RESPAN_API_KEY) {
  throw new Error("Set RESPAN_API_KEY to run this example.");
}

const client = new Anthropic({
  // The official Anthropic SDK appends `/v1/messages`, so point it at the
  // gateway's `/anthropic` passthrough path.
  apiKey: RESPAN_API_KEY,
  baseURL: ANTHROPIC_BASE_URL,
});

const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  appName: "anthropic-sdk-complex-edge-cases",
  instrumentations: [new AnthropicInstrumentor()],
});

const WEATHER_TOOL: Anthropic.Tool = {
  name: "get_weather",
  description: "Get current weather information for a city.",
  input_schema: {
    type: "object",
    properties: {
      city: { type: "string" },
      unit: { type: "string", enum: ["celsius", "fahrenheit"] },
    },
    required: ["city"],
  },
};

const CUSTOMER_TOOL: Anthropic.Tool = {
  name: "lookup_customer_profile",
  description: "Look up a customer profile and return plan status information.",
  input_schema: {
    type: "object",
    properties: {
      customer_id: { type: "string" },
    },
    required: ["customer_id"],
  },
};

type SummaryRecord = Record<string, unknown>;

function extractText(content: Anthropic.Message["content"]): string {
  return content
    .filter((block): block is Anthropic.TextBlock => block.type === "text")
    .map((block) => block.text)
    .join("\n");
}

function summarizeToolUses(message: Anthropic.Message): SummaryRecord[] {
  return message.content
    .filter((block): block is Anthropic.ToolUseBlock => block.type === "tool_use")
    .map((block) => ({
      id: block.id,
      name: block.name,
      input: block.input,
    }));
}

function summarizeMessage(message: Anthropic.Message): SummaryRecord {
  return {
    id: message.id,
    model: message.model,
    stop_reason: message.stop_reason,
    text: extractText(message.content),
    usage: message.usage,
    tool_uses: summarizeToolUses(message),
  };
}

function assistantContentToParams(
  content: Anthropic.Message["content"],
): Anthropic.ContentBlockParam[] {
  const params: Anthropic.ContentBlockParam[] = [];

  for (const block of content) {
    if (block.type === "text") {
      params.push({ type: "text", text: block.text });
      continue;
    }

    if (block.type === "tool_use") {
      params.push({
        type: "tool_use",
        id: block.id,
        name: block.name,
        input: block.input,
      });
    }
  }

  return params;
}

function buildWeatherResult(input: Record<string, unknown>): string {
  const city = String(input.city ?? "unknown");
  const unit = input.unit === "fahrenheit" ? "fahrenheit" : "celsius";
  const temperature = unit === "fahrenheit" ? "72F" : "22C";
  return JSON.stringify({
    city,
    temperature,
    condition: "Sunny",
    humidity: "45%",
  });
}

function buildCustomerResult(
  input: Record<string, unknown>,
): { content: string; isError?: boolean } {
  const customerId = String(input.customer_id ?? "unknown");

  if (customerId !== "cust_123") {
    return {
      content: `Customer ${customerId} was not found in the demo CRM.`,
      isError: true,
    };
  }

  return {
    content: JSON.stringify({
      customer_id: customerId,
      plan: "enterprise",
      health: "green",
      renewal_month: "2026-09",
    }),
  };
}

function executeDemoTool(
  toolUse: Anthropic.ToolUseBlock,
): { content: string; isError?: boolean } {
  const input =
    toolUse.input && typeof toolUse.input === "object" && !Array.isArray(toolUse.input)
      ? (toolUse.input as Record<string, unknown>)
      : {};

  if (toolUse.name === WEATHER_TOOL.name) {
    return { content: buildWeatherResult(input) };
  }

  if (toolUse.name === CUSTOMER_TOOL.name) {
    return buildCustomerResult(input);
  }

  return {
    content: `Unsupported tool: ${toolUse.name}`,
    isError: true,
  };
}

function buildToolResultBlocks(
  toolUses: Anthropic.ToolUseBlock[],
): Anthropic.ToolResultBlockParam[] {
  return toolUses.map((toolUse) => {
    const result = executeDemoTool(toolUse);
    return {
      type: "tool_result",
      tool_use_id: toolUse.id,
      content: result.content,
      ...(result.isError ? { is_error: true } : {}),
    };
  });
}

function snippet(value: string, maxLength = 160): string {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}...`;
}

async function runBasicCreate(): Promise<SummaryRecord> {
  return respan.withTask({ name: "messages_create_basic" }, async () => {
    const message = await client.messages.create({
      model: ANTHROPIC_MODEL,
      max_tokens: 160,
      system: [{ type: "text", text: "You are terse and precise." }],
      messages: [
        {
          role: "user",
          content: [
            {
              type: "text",
              text: "In one sentence, explain why tracing helps debugging.",
            },
          ],
        },
      ],
    });

    const summary = summarizeMessage(message);
    console.log(`  [basic] ${snippet(String(summary.text ?? ""))}`);
    return summary;
  });
}

async function runStreamingCreate(): Promise<SummaryRecord> {
  return respan.withTask({ name: "messages_create_stream_true" }, async () => {
    const stream = await client.messages.create({
      model: ANTHROPIC_MODEL,
      max_tokens: 180,
      stream: true,
      messages: [
        {
          role: "user",
          content: "Write a short haiku about instrumentation.",
        },
      ],
    });

    const eventTypes: string[] = [];
    let textDelta = "";

    for await (const event of stream) {
      eventTypes.push(event.type);
      if (
        event.type === "content_block_delta" &&
        event.delta.type === "text_delta"
      ) {
        textDelta += event.delta.text;
      }
    }

    console.log(`  [stream:true] events=${eventTypes.join(" -> ")}`);
    return {
      event_types: eventTypes,
      text_preview: snippet(textDelta),
    };
  });
}

async function runStreamHelper(): Promise<SummaryRecord> {
  return respan.withTask({ name: "messages_stream_helper" }, async () => {
    const textChunks: string[] = [];
    const stream = client.messages
      .stream({
        model: ANTHROPIC_MODEL,
        max_tokens: 180,
        messages: [
          {
            role: "user",
            content: "List three trace debugging benefits as short bullets.",
          },
        ],
      })
      .on("text", (textDelta) => {
        textChunks.push(textDelta);
      });

    const finalMessage = await stream.finalMessage();
    const summary = summarizeMessage(finalMessage);

    console.log(`  [messages.stream] ${snippet(String(summary.text ?? ""))}`);
    return {
      text_delta_count: textChunks.length,
      final_message: summary,
    };
  });
}

async function runToolSuccessRoundTrip(): Promise<SummaryRecord> {
  return respan.withTask({ name: "messages_create_tool_success_roundtrip" }, async () => {
    const initial = await client.messages.create({
      model: ANTHROPIC_MODEL,
      max_tokens: 220,
      tool_choice: { type: "tool", name: WEATHER_TOOL.name },
      tools: [WEATHER_TOOL],
      messages: [
        {
          role: "user",
          content:
            "Use the get_weather tool for Tokyo, then give me a short travel tip.",
        },
      ],
    });

    const toolUses = initial.content.filter(
      (block): block is Anthropic.ToolUseBlock => block.type === "tool_use",
    );
    if (toolUses.length === 0) {
      throw new Error("Expected get_weather tool_use block but none were returned.");
    }

    const toolResults = buildToolResultBlocks(toolUses);
    const finalMessage = await client.messages.create({
      model: ANTHROPIC_MODEL,
      max_tokens: 220,
      tools: [WEATHER_TOOL],
      messages: [
        {
          role: "user",
          content:
            "Use the get_weather tool for Tokyo, then give me a short travel tip.",
        },
        {
          role: "assistant",
          content: assistantContentToParams(initial.content),
        },
        {
          role: "user",
          content: toolResults,
        },
      ],
    });

    const summary = {
      initial_message: summarizeMessage(initial),
      tool_results: toolResults,
      final_message: summarizeMessage(finalMessage),
    };

    console.log(
      `  [tool success] tool_results=${toolResults.length}, final=${snippet(String(summary.final_message.text ?? ""))}`,
    );
    return summary;
  });
}

async function runToolErrorRoundTrip(): Promise<SummaryRecord> {
  return respan.withTask({ name: "messages_create_tool_error_roundtrip" }, async () => {
    const initial = await client.messages.create({
      model: ANTHROPIC_MODEL,
      max_tokens: 220,
      tool_choice: { type: "tool", name: CUSTOMER_TOOL.name },
      tools: [CUSTOMER_TOOL],
      messages: [
        {
          role: "user",
          content:
            "Use lookup_customer_profile for customer_id cust_404 and explain what happened.",
        },
      ],
    });

    const toolUses = initial.content.filter(
      (block): block is Anthropic.ToolUseBlock => block.type === "tool_use",
    );
    if (toolUses.length === 0) {
      throw new Error(
        "Expected lookup_customer_profile tool_use block but none were returned.",
      );
    }

    const toolResults = buildToolResultBlocks(toolUses);
    const finalMessage = await client.messages.create({
      model: ANTHROPIC_MODEL,
      max_tokens: 220,
      tools: [CUSTOMER_TOOL],
      messages: [
        {
          role: "user",
          content:
            "Use lookup_customer_profile for customer_id cust_404 and explain what happened.",
        },
        {
          role: "assistant",
          content: assistantContentToParams(initial.content),
        },
        {
          role: "user",
          content: toolResults,
        },
      ],
    });

    const summary = {
      initial_message: summarizeMessage(initial),
      tool_results: toolResults,
      final_message: summarizeMessage(finalMessage),
    };

    console.log(
      `  [tool error] tool_results=${toolResults.length}, final=${snippet(String(summary.final_message.text ?? ""))}`,
    );
    return summary;
  });
}

async function runExpectedRequestError(): Promise<SummaryRecord> {
  return respan.withTask({ name: "messages_create_expected_error" }, async () => {
    try {
      await client.messages.create({
        model: "claude-invalid-model" as Anthropic.Model,
        max_tokens: 64,
        messages: [
          {
            role: "user",
            content: "This request should fail with an invalid model.",
          },
        ],
      });

      return { unexpected_success: true };
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.log(`  [expected error] ${snippet(message)}`);
      return { error_message: message };
    }
  });
}

async function runWorkflow(): Promise<SummaryRecord> {
  return respan.withWorkflow(
    { name: "anthropic_sdk_complex_edge_cases" },
    async () => ({
      messages_create_basic: await runBasicCreate(),
      messages_create_stream_true: await runStreamingCreate(),
      messages_stream_helper: await runStreamHelper(),
      messages_create_tool_success_roundtrip: await runToolSuccessRoundTrip(),
      messages_create_tool_error_roundtrip: await runToolErrorRoundTrip(),
      messages_create_expected_error: await runExpectedRequestError(),
    }),
  );
}

function printSummary(results: SummaryRecord): void {
  console.log(`\n${"=".repeat(60)}`);
  console.log("SUMMARY");
  console.log(`${"=".repeat(60)}`);
  console.log(`Customer identifier: ${CUSTOMER_IDENTIFIER}`);
  console.log(`Example name:        ${EXAMPLE_NAME}`);
  console.log(`Model:               ${ANTHROPIC_MODEL}`);
  console.log(`Respan base URL:     ${RESPAN_BASE_URL}`);
  console.log(`Gateway base URL:    ${RESPAN_GATEWAY_BASE_URL}`);
  console.log(`Anthropic base URL:  ${ANTHROPIC_BASE_URL}`);
  console.log();

  for (const [name, value] of Object.entries(results)) {
    const record =
      value && typeof value === "object" && !Array.isArray(value)
        ? (value as SummaryRecord)
        : {};

    if (name === "messages_create_stream_true") {
      const eventTypes = Array.isArray(record.event_types)
        ? record.event_types.join(" -> ")
        : "unknown";
      console.log(`- ${name}: ${eventTypes}`);
      continue;
    }

    if ("final_message" in record) {
      const finalMessage =
        record.final_message &&
        typeof record.final_message === "object" &&
        !Array.isArray(record.final_message)
          ? (record.final_message as SummaryRecord)
          : {};
      console.log(
        `- ${name}: stop=${String(finalMessage.stop_reason ?? "unknown")}, text=${snippet(String(finalMessage.text ?? ""))}`,
      );
      continue;
    }

    if ("error_message" in record) {
      console.log(`- ${name}: ${snippet(String(record.error_message ?? ""))}`);
      continue;
    }

    if ("text" in record) {
      console.log(
        `- ${name}: stop=${String(record.stop_reason ?? "unknown")}, text=${snippet(String(record.text ?? ""))}`,
      );
      continue;
    }

    console.log(`- ${name}: completed`);
  }

  console.log("\nCheck traces in Respan with:");
  console.log(`  customer_identifier = ${CUSTOMER_IDENTIFIER}`);
  console.log(`  metadata.example_name = ${EXAMPLE_NAME}`);
}

async function main(): Promise<void> {
  await respan.initialize();

  try {
    const results = await respan.propagateAttributes(
      {
        customer_identifier: CUSTOMER_IDENTIFIER,
        metadata: {
          example_name: EXAMPLE_NAME,
          sdk: "anthropic-typescript-sdk",
          gateway_routed: true,
          local_instrumentation: true,
        },
      },
      async () => runWorkflow(),
    );

    printSummary(results);
  } finally {
    await respan.flush();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
