import * as _ClaudeAgentSDK from "@anthropic-ai/claude-agent-sdk";
import type { Options, SDKMessage } from "@anthropic-ai/claude-agent-sdk";
import { createSdkMcpServer, tool } from "@anthropic-ai/claude-agent-sdk";
import type { Respan } from "@respan/respan";
import { z } from "zod";

import {
  buildBaseQueryOptions,
  createRespan,
  printCommonSummary,
} from "./_shared.js";

const ClaudeAgentSDK = { ..._ClaudeAgentSDK };

const CUSTOMER_IDENTIFIER = "claude-agent-sdk-complex-edge-cases-v2";
const EXAMPLE_NAME = "claude_agent_sdk_complex_edge_cases";
const APP_NAME = "claude-agent-sdk-complex-edge-cases";

const TOOL_SYSTEM_PROMPT =
  "You have access to demo MCP tools. When the user asks for information that a tool can provide, call the tool before answering. Keep the final answer concise.";
const MULTI_TOOL_SYSTEM_PROMPT =
  "You have access to demo MCP tools. If the user asks for multiple facts that map to multiple tools, call every relevant tool before giving the final answer.";

function textToolResult(text: string, isError = false) {
  return {
    content: [{ type: "text" as const, text }],
    ...(isError ? { isError: true } : {}),
  };
}

const getWeatherTool = tool(
  "get_weather",
  "Get current weather information for a city.",
  {
    city: z.string(),
    unit: z.string().optional(),
  },
  async ({ city, unit }) => {
    const normalizedUnit = unit || "celsius";
    const temperature = normalizedUnit === "celsius" ? "22C" : "72F";
    return textToolResult(
      JSON.stringify({
        city,
        temperature,
        condition: "Sunny",
        humidity: "45%",
      }),
    );
  },
);

const calculatorTool = tool(
  "calculator",
  "Evaluate a mathematical expression and return the numeric result.",
  {
    expression: z.string(),
  },
  async ({ expression }) => {
    if (!/^[0-9+\-*/ ().]+$/.test(expression)) {
      return textToolResult("Calculator error: unsupported characters.", true);
    }

    try {
      const result = Function(`"use strict"; return (${expression});`)();
      return textToolResult(String(result));
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      return textToolResult(`Calculator error: ${message}`, true);
    }
  },
);

const webSearchTool = tool(
  "web_search",
  "Return a short mock search result list for a query.",
  {
    query: z.string(),
    max_results: z.number().int().optional(),
  },
  async ({ query, max_results }) => {
    const results = [
      {
        title: `Result about ${query}`,
        snippet: `Detailed info on ${query}...`,
      },
      {
        title: `${query} - Wikipedia`,
        snippet: "From the free encyclopedia...",
      },
    ];

    const limit = Math.max(1, Math.min(max_results ?? 2, results.length));
    return textToolResult(JSON.stringify(results.slice(0, limit)));
  },
);

const lookupCustomerProfileTool = tool(
  "lookup_customer_profile",
  "Look up a customer profile and return an error for unknown IDs.",
  {
    customer_id: z.string(),
  },
  async ({ customer_id }) => {
    if (customer_id !== "cust_123") {
      return textToolResult(
        `Customer ${customer_id} was not found in the demo CRM.`,
        true,
      );
    }

    return textToolResult(
      JSON.stringify({
        customer_id,
        plan: "enterprise",
        health: "green",
        renewal_month: "2026-09",
      }),
    );
  },
);

const DEMO_MCP_SERVER = createSdkMcpServer({
  name: "respan_demo_tools",
  version: "1.0.0",
  tools: [
    getWeatherTool,
    calculatorTool,
    webSearchTool,
    lookupCustomerProfileTool,
  ],
});

type QueryRunResult = {
  prompt: string;
  sessionId?: string;
  messageTypes: string[];
  messages: Array<Record<string, unknown>>;
  result?: Record<string, unknown>;
};

function buildOptions(options: {
  includeDemoTools?: boolean;
  systemPrompt?: string;
  maxTurns?: number;
  resume?: string;
} = {}): Options {
  return buildBaseQueryOptions({
    maxTurns: options.maxTurns ?? 4,
    systemPrompt: options.systemPrompt,
    resume: options.resume,
    tools: [],
    mcpServers: options.includeDemoTools ? { demo: DEMO_MCP_SERVER } : {},
  });
}

function snippet(value: string, maxLength = 160): string {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}...`;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function serializeContentBlock(block: unknown): Record<string, unknown> {
  const data = asRecord(block) || {};
  const type = typeof data.type === "string" ? data.type : "unknown";

  if (type === "text") {
    return {
      type,
      text: typeof data.text === "string" ? data.text : "",
    };
  }

  if (type === "tool_use") {
    return {
      type,
      id: data.id,
      name: data.name,
      input: data.input,
    };
  }

  if (type === "tool_result") {
    return {
      type,
      tool_use_id: data.tool_use_id,
      content: data.content,
      is_error: data.is_error,
    };
  }

  return {
    type,
    value: data,
  };
}

function extractTextFromContent(content: unknown): string {
  if (typeof content === "string") {
    return content;
  }

  if (!Array.isArray(content)) {
    return "";
  }

  const parts: string[] = [];
  for (const block of content) {
    const data = asRecord(block);
    if (!data) {
      continue;
    }

    if (data.type === "text" && typeof data.text === "string") {
      parts.push(data.text);
      continue;
    }

    if (data.type === "tool_result") {
      if (typeof data.content === "string") {
        parts.push(data.content);
        continue;
      }
      if (Array.isArray(data.content)) {
        parts.push(extractTextFromContent(data.content));
      }
    }
  }

  return parts.filter(Boolean).join("\n");
}

function serializeMessage(message: SDKMessage): Record<string, unknown> {
  if (message.type === "assistant") {
    return {
      type: message.type,
      model: message.message.model,
      parent_tool_use_id: message.parent_tool_use_id,
      content: Array.isArray(message.message.content)
        ? message.message.content.map((block) => serializeContentBlock(block))
        : message.message.content,
    };
  }

  if (message.type === "user") {
    const content = asRecord(message.message)?.content;
    return {
      type: message.type,
      parent_tool_use_id: message.parent_tool_use_id,
      tool_use_result: message.tool_use_result,
      isSynthetic: message.isSynthetic,
      content: Array.isArray(content)
        ? content.map((block) => serializeContentBlock(block))
        : content,
    };
  }

  if (message.type === "system") {
    const summary: Record<string, unknown> = {
      type: message.type,
      subtype: message.subtype,
      session_id: message.session_id,
    };

    if ("state" in message) {
      summary.state = message.state;
    }
    if ("text" in message) {
      summary.text = message.text;
    }
    if ("status" in message) {
      summary.status = message.status;
    }

    return summary;
  }

  if (message.type === "result") {
    return {
      type: message.type,
      subtype: message.subtype,
      duration_ms: message.duration_ms,
      duration_api_ms: message.duration_api_ms,
      is_error: message.is_error,
      num_turns: message.num_turns,
      stop_reason: message.stop_reason,
      total_cost_usd: message.total_cost_usd,
      usage: message.usage,
      session_id: message.session_id,
      result: "result" in message ? message.result : undefined,
      errors: "errors" in message ? message.errors : undefined,
    };
  }

  if (message.type === "tool_progress") {
    return {
      type: message.type,
      tool_name: message.tool_name,
      tool_use_id: message.tool_use_id,
      elapsed_time_seconds: message.elapsed_time_seconds,
      session_id: message.session_id,
    };
  }

  if (message.type === "tool_use_summary") {
    return {
      type: message.type,
      summary: message.summary,
      session_id: message.session_id,
    };
  }

  return {
    type: message.type,
    session_id: "session_id" in message ? message.session_id : undefined,
  };
}

function printStreamMessage(message: SDKMessage): void {
  if (message.type === "system") {
    console.log(`    [System] subtype=${message.subtype}`);
    return;
  }

  if (message.type === "assistant") {
    const content = Array.isArray(message.message.content)
      ? message.message.content
      : [];

    for (const block of content) {
      const data = asRecord(block);
      if (!data || typeof data.type !== "string") {
        continue;
      }

      if (data.type === "text" && typeof data.text === "string") {
        console.log(`    [Assistant] ${snippet(data.text)}`);
        continue;
      }

      if (data.type === "tool_use") {
        console.log(
          `    [ToolUse] ${String(data.name)}(${JSON.stringify(data.input)})`,
        );
      }
    }
    return;
  }

  if (message.type === "user" && message.parent_tool_use_id) {
    const contentText = extractTextFromContent(asRecord(message.message)?.content);
    console.log(
      `    [UserToolResult] ${message.parent_tool_use_id}: ${snippet(contentText)}`,
    );
    return;
  }

  if (message.type === "tool_progress") {
    console.log(`    [ToolProgress] ${message.tool_name} (${message.tool_use_id})`);
    return;
  }

  if (message.type === "tool_use_summary") {
    console.log(`    [ToolSummary] ${snippet(message.summary)}`);
    return;
  }

  if (message.type === "result") {
    console.log(
      `    [Result] subtype=${message.subtype}, stop=${String(message.stop_reason)}, turns=${message.num_turns}, session=${message.session_id}`,
    );
    if ("result" in message && message.result) {
      console.log(`    [ResultText] ${snippet(message.result)}`);
    }
    if ("errors" in message && message.errors.length > 0) {
      console.log(`    [Errors] ${snippet(message.errors.join("; "))}`);
    }
    return;
  }

  console.log(`    [${message.type}]`);
}

async function runQueryCollect(args: {
  prompt: string;
  options: Options;
}): Promise<QueryRunResult> {
  const stream = await ClaudeAgentSDK.query({
    prompt: args.prompt,
    options: args.options,
  });

  const messageTypes: string[] = [];
  const messages: Array<Record<string, unknown>> = [];
  let resultSummary: Record<string, unknown> | undefined;
  let sessionId: string | undefined;

  for await (const message of stream) {
    printStreamMessage(message);
    messageTypes.push(message.type);
    messages.push(serializeMessage(message));
    if ("session_id" in message) {
      sessionId = message.session_id;
    }
    if (message.type === "result") {
      resultSummary = serializeMessage(message);
    }
  }

  return {
    prompt: args.prompt,
    sessionId,
    messageTypes,
    messages,
    result: resultSummary,
  };
}

async function runScenario<T>(name: string, fn: () => Promise<T>): Promise<T> {
  console.log(`\n${"-".repeat(60)}`);
  console.log(`  SCENARIO: ${name}`);
  console.log(`${"-".repeat(60)}`);
  const result = await fn();
  console.log(`  completed: ${name}`);
  return result;
}

async function scenarioBasicQuery(respan: Respan): Promise<QueryRunResult> {
  return respan.withTask({ name: "basic_query" }, async () =>
    runScenario("basic_query", async () =>
      runQueryCollect({
        prompt: "Explain in two short sentences what Claude Agent SDK tracing gives me.",
        options: buildOptions({ maxTurns: 2 }),
      }),
    ),
  );
}

async function scenarioSingleToolQuery(respan: Respan): Promise<QueryRunResult> {
  return respan.withTask({ name: "single_tool_query" }, async () =>
    runScenario("single_tool_query", async () =>
      runQueryCollect({
        prompt:
          "Use the get_weather tool to check Tokyo weather, then summarize the result in two bullet points.",
        options: buildOptions({
          includeDemoTools: true,
          systemPrompt: TOOL_SYSTEM_PROMPT,
          maxTurns: 4,
        }),
      }),
    ),
  );
}

async function scenarioMultiToolQuery(respan: Respan): Promise<QueryRunResult> {
  return respan.withTask({ name: "multi_tool_query" }, async () =>
    runScenario("multi_tool_query", async () =>
      runQueryCollect({
        prompt:
          "Use get_weather for Paris, calculator for 84.50 * 0.15, and web_search for best restaurants in Paris. Then give me a concise trip summary.",
        options: buildOptions({
          includeDemoTools: true,
          systemPrompt: MULTI_TOOL_SYSTEM_PROMPT,
          maxTurns: 6,
        }),
      }),
    ),
  );
}

async function scenarioToolErrorQuery(respan: Respan): Promise<QueryRunResult> {
  return respan.withTask({ name: "tool_error_query" }, async () =>
    runScenario("tool_error_query", async () =>
      runQueryCollect({
        prompt:
          "Use the lookup_customer_profile tool for customer_id cust_404 and tell me briefly what happened.",
        options: buildOptions({
          includeDemoTools: true,
          systemPrompt: TOOL_SYSTEM_PROMPT,
          maxTurns: 4,
        }),
      }),
    ),
  );
}

async function scenarioMultiTurnWithResume(
  respan: Respan,
): Promise<Record<string, unknown>> {
  return respan.withTask({ name: "query_resume_multi_turn_with_tools" }, async () =>
    runScenario("query_resume_multi_turn_with_tools", async () => {
      const prompts = [
        "Remember that my name is Alex and my favorite city is Kyoto.",
        "What are my name and favorite city? Use get_weather for Kyoto and answer briefly.",
        "Use web_search to find one popular attraction in Kyoto and recommend it in one sentence.",
        "Use lookup_customer_profile for customer_id cust_404 and tell me briefly what happened.",
        "Now use calculator for 120 * 0.15 and answer in one sentence with the tip amount.",
      ];

      let sessionId: string | undefined;
      const turns: QueryRunResult[] = [];

      for (const prompt of prompts) {
        console.log(`    [User] ${prompt}`);
        const turn = await runQueryCollect({
          prompt,
          options: buildOptions({
            includeDemoTools: true,
            systemPrompt: MULTI_TOOL_SYSTEM_PROMPT,
            maxTurns: 6,
            resume: sessionId,
          }),
        });
        sessionId = turn.sessionId || sessionId;
        turns.push(turn);
      }

      return {
        session_id: sessionId,
        turns,
      };
    }),
  );
}

async function runComplexWorkflow(respan: Respan): Promise<Record<string, unknown>> {
  return respan.withWorkflow(
    { name: "claude_agent_sdk_complex_edge_cases" },
    async () => ({
      basic_query: await scenarioBasicQuery(respan),
      single_tool_query: await scenarioSingleToolQuery(respan),
      multi_tool_query: await scenarioMultiToolQuery(respan),
      tool_error_query: await scenarioToolErrorQuery(respan),
      query_resume_multi_turn_with_tools: await scenarioMultiTurnWithResume(respan),
    }),
  );
}

function printSummary(results: Record<string, unknown>): void {
  console.log(`\n${"=".repeat(60)}`);
  console.log("SUMMARY");
  console.log(`${"=".repeat(60)}`);
  console.log(`Customer identifier: ${CUSTOMER_IDENTIFIER}`);

  for (const [scenarioName, scenarioValue] of Object.entries(results)) {
    const scenario = asRecord(scenarioValue) || {};
    if (scenarioName === "query_resume_multi_turn_with_tools") {
      const turns = Array.isArray(scenario.turns) ? scenario.turns : [];
      console.log(
        `- ${scenarioName}: ${turns.length} turns, session=${String(scenario.session_id ?? "unknown")}`,
      );
      continue;
    }

    const messages = Array.isArray(scenario.messages) ? scenario.messages : [];
    const result = asRecord(scenario.result) || {};
    console.log(
      `- ${scenarioName}: messages=${messages.length}, session=${String(result.session_id ?? "unknown")}, stop=${String(result.stop_reason ?? "unknown")}`,
    );
  }

  printCommonSummary({
    title: "Trace Lookup",
    customerIdentifier: CUSTOMER_IDENTIFIER,
    exampleName: EXAMPLE_NAME,
  });
}

async function main(): Promise<void> {
  const respan = createRespan({
    appName: APP_NAME,
    sdkModule: ClaudeAgentSDK,
  });

  await respan.initialize();

  try {
    const results = await respan.propagateAttributes(
      {
        customer_identifier: CUSTOMER_IDENTIFIER,
        metadata: {
          example_name: EXAMPLE_NAME,
          sdk: "claude-agent-sdk",
          local_instrumentation: true,
          example_type: "advanced",
        },
      },
      async () => runComplexWorkflow(respan),
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
