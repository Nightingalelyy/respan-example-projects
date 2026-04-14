/** MCP — Client calling a tool on a stdio server, traced via OpenInference.
 *
 * Both client and server are instrumented with @arizeai/openinference-instrumentation-mcp.
 * The MCP instrumentation propagates W3C trace context through JSON-RPC _meta,
 * linking client and server spans into a single distributed trace.
 */

import "dotenv/config";
import { trace } from "@opentelemetry/api";
import { MCPInstrumentation } from "@arizeai/openinference-instrumentation-mcp";
import { Respan, withWorkflow, withTool } from "@respan/respan";
import { OpenInferenceInstrumentor } from "@respan/instrumentation-openinference";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY;
const RESPAN_BASE_URL = (process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api").replace(/\/+$/, "");

const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
  instrumentations: [new OpenInferenceInstrumentor(MCPInstrumentation)],
});
await respan.initialize();

const MCPClientModule = await import("@modelcontextprotocol/sdk/client/index.js");
const MCPClientStdioModule = await import("@modelcontextprotocol/sdk/client/stdio.js");

const mcpInst = new MCPInstrumentation();
mcpInst.setTracerProvider(trace.getTracerProvider());
mcpInst.manuallyInstrument({ clientStdioModule: MCPClientStdioModule });

const transport = new MCPClientStdioModule.StdioClientTransport({
  command: "npx",
  args: ["tsx", new URL("./server.ts", import.meta.url).pathname],
  env: { ...process.env } as Record<string, string>,
});

const client = new MCPClientModule.Client({ name: "test-client", version: "1.0.0" });

await withWorkflow({ name: "mcp-hello-workflow" }, async () => {
  await client.connect(transport);

  const tools = await withTool({ name: "mcp.listTools" }, async () => {
    return client.listTools();
  });
  console.log("Available tools:", tools.tools.map((t: any) => t.name));

  const result = await withTool({ name: "mcp.callTool:hello" }, async () => {
    return client.callTool({ name: "hello", arguments: { name: "Respan" } });
  });
  console.log("Tool result:", (result.content as any)[0].text);

  await client.close();
});

await respan.flush();
