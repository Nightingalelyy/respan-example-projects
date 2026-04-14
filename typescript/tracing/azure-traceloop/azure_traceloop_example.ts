/**
 * Azure OpenAI — Chat completion with Respan tracing via Traceloop.
 *
 * The @azure/openai v1.x SDK sends requests to Azure-format URLs:
 *   {endpoint}/openai/deployments/{model}/chat/completions?api-version=...
 *
 * Since the Respan gateway expects the standard OpenAI format
 *   ({baseURL}/chat/completions), a tiny local proxy rewrites the URL.
 *
 * The @traceloop/instrumentation-azure patches OpenAIClient.getChatCompletions
 * and OpenAIClient.getCompletions to create Traceloop-format OTel spans.
 */

import "dotenv/config";
import http from "node:http";
import https from "node:https";
import { URL } from "node:url";
import { trace } from "@opentelemetry/api";
import { AzureOpenAIInstrumentation } from "@traceloop/instrumentation-azure";
import * as AzureOpenAIModule from "@azure/openai";
import { OpenAIClient, AzureKeyCredential } from "@azure/openai";
import { Respan } from "@respan/respan";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api").replace(/\/+$/, "");

// ── 1. Initialize Respan tracing ──────────────────────────────────────
const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
});
await respan.initialize();

// ── 2. Manually instrument @azure/openai ──────────────────────────────
const instrumentation = new AzureOpenAIInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument(AzureOpenAIModule);

// ── 3. Local proxy: rewrites Azure-format URLs to standard OpenAI ─────
function startProxy(targetBase: string, apiKey: string): Promise<string> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const match = req.url?.match(/\/openai\/deployments\/([^/]+)\/chat\/completions/);
      const model = match?.[1] ?? "gpt-4o-mini";
      const target = new URL(`${targetBase}/chat/completions`);

      const chunks: Buffer[] = [];
      req.on("data", (c) => chunks.push(c));
      req.on("end", () => {
        const body = JSON.parse(Buffer.concat(chunks).toString());
        body.model = model;
        const payload = JSON.stringify(body);

        const options: https.RequestOptions = {
          hostname: target.hostname,
          port: target.port || (target.protocol === "https:" ? 443 : 80),
          path: target.pathname,
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(payload),
            Authorization: `Bearer ${apiKey}`,
          },
        };

        const transport = target.protocol === "https:" ? https : http;
        const upstream = transport.request(options, (upRes) => {
          res.writeHead(upRes.statusCode ?? 200, upRes.headers);
          upRes.pipe(res);
        });
        upstream.on("error", (e) => {
          res.writeHead(502);
          res.end(JSON.stringify({ error: e.message }));
        });
        upstream.write(payload);
        upstream.end();
      });
    });
    server.listen(0, () => {
      const port = (server.address() as any).port;
      (globalThis as any).__azureProxy = server;
      resolve(`http://localhost:${port}`);
    });
  });
}

const proxyUrl = await startProxy(RESPAN_BASE_URL, RESPAN_API_KEY);

// ── 4. Create Azure OpenAI client pointing at local proxy ─────────────
const client = new OpenAIClient(
  proxyUrl,
  new AzureKeyCredential(RESPAN_API_KEY),
  { allowInsecureConnection: true },
);

const result = await client.getChatCompletions("gpt-4o-mini", [
  { role: "user", content: "Write a haiku about recursion in programming." },
]);

console.log(result.choices[0]?.message?.content);

// ── 5. Flush and cleanup ──────────────────────────────────────────────
await respan.flush();
((globalThis as any).__azureProxy as http.Server).close();
