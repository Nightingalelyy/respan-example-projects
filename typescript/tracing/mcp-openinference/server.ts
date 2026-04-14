/** MCP server with OpenTelemetry tracing — spans are exported to Respan. */

import "dotenv/config";
import { trace, SpanKind, SpanStatusCode } from "@opentelemetry/api";
import { MCPInstrumentation } from "@arizeai/openinference-instrumentation-mcp";
import * as MCPServerStdioModule from "@modelcontextprotocol/sdk/server/stdio.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { Respan } from "@respan/respan";
import { OpenInferenceInstrumentor } from "@respan/instrumentation-openinference";
import { z } from "zod";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY;
const RESPAN_BASE_URL = (process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api").replace(/\/+$/, "");

const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  instrumentations: [new OpenInferenceInstrumentor(MCPInstrumentation)],
});
await respan.initialize();

const mcpInst = new MCPInstrumentation();
mcpInst.setTracerProvider(trace.getTracerProvider());
mcpInst.manuallyInstrument({ serverStdioModule: MCPServerStdioModule });

const tracer = trace.getTracer("mcp-server");
const server = new McpServer({ name: "hello-server", version: "1.0.0" });

server.tool("hello", { name: z.string() }, async ({ name }) => {
  return tracer.startActiveSpan("tool:hello", { kind: SpanKind.SERVER }, (span) => {
    span.setAttribute("mcp.tool.name", "hello");
    span.setAttribute("mcp.tool.input", JSON.stringify({ name }));
    const text = `Hello, ${name}! Recursion is when a function calls itself.`;
    span.setAttribute("mcp.tool.output", text);
    span.setStatus({ code: SpanStatusCode.OK });
    span.end();
    return { content: [{ type: "text" as const, text }] };
  });
});

const transport = new MCPServerStdioModule.StdioServerTransport();
await server.connect(transport);

process.on("SIGINT", async () => {
  await respan.flush();
  process.exit(0);
});
