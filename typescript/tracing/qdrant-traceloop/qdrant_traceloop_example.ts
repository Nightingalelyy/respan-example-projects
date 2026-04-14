/**
 * Qdrant — Vector DB operations with Respan tracing via Traceloop.
 *
 * Since we don't have a real Qdrant server, a local HTTP mock server
 * simulates the Qdrant REST API (upsert + search). The SDK is pointed
 * at it via the url parameter.
 *
 * The @traceloop/instrumentation-qdrant patches QdrantClient.prototype
 * methods (upsert, retrieve, search, delete) to create Traceloop-format
 * OTel spans.
 */

import "dotenv/config";
import http from "node:http";
import { trace } from "@opentelemetry/api";
import { QdrantInstrumentation } from "@traceloop/instrumentation-qdrant";
import * as QdrantModule from "@qdrant/js-client-rest";
import { QdrantClient } from "@qdrant/js-client-rest";
import { Respan } from "@respan/respan";

const RESPAN_API_KEY = process.env.RESPAN_API_KEY!;
const RESPAN_BASE_URL = (
  process.env.RESPAN_BASE_URL ?? "https://api.respan.ai/api"
).replace(/\/+$/, "");

// ── 1. Initialize Respan tracing ──────────────────────────────────────
const respan = new Respan({
  apiKey: RESPAN_API_KEY,
  baseURL: RESPAN_BASE_URL,
});
await respan.initialize();

// ── 2. Manually instrument @qdrant/js-client-rest ─────────────────────
const instrumentation = new QdrantInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument(QdrantModule);

// ── 3. Local mock Qdrant server ───────────────────────────────────────
function startMockQdrant(): Promise<string> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const chunks: Buffer[] = [];
      req.on("data", (c: Buffer) => chunks.push(c));
      req.on("end", () => {
        res.writeHead(200, { "Content-Type": "application/json" });

        // Version check (initial GET /)
        if (req.method === "GET" && req.url === "/") {
          res.end(
            JSON.stringify({
              title: "qdrant - vectorass engine",
              version: "1.17.0",
            })
          );
          return;
        }

        // Upsert points
        if (req.url?.includes("/points") && req.method === "PUT") {
          res.end(
            JSON.stringify({
              result: { operation_id: 1, status: "completed" },
              status: "ok",
              time: 0.001,
            })
          );
          return;
        }

        // Search points
        if (req.url?.includes("/points/search")) {
          res.end(
            JSON.stringify({
              result: [
                {
                  id: 1,
                  score: 0.97,
                  version: 1,
                  payload: { text: "recursion in programming" },
                },
                {
                  id: 3,
                  score: 0.82,
                  version: 1,
                  payload: { text: "algorithm design" },
                },
              ],
              status: "ok",
              time: 0.001,
            })
          );
          return;
        }

        // Collection info
        if (req.url?.includes("/collections")) {
          res.end(
            JSON.stringify({
              result: {
                status: "green",
                optimizer_status: "ok",
                vectors_count: 3,
                points_count: 3,
              },
              status: "ok",
              time: 0.001,
            })
          );
          return;
        }

        res.end(JSON.stringify({ status: "ok" }));
      });
    });

    server.listen(0, () => {
      const port = (server.address() as any).port;
      (globalThis as any).__qdrantServer = server;
      resolve(`http://localhost:${port}`);
    });
  });
}

const mockUrl = await startMockQdrant();

// ── 4. Create Qdrant client pointing at mock server ───────────────────
const client = new QdrantClient({
  url: mockUrl,
  checkCompatibility: false,
});

// Wrap in a Respan workflow so child spans pass through the filter
await respan.withWorkflow({ name: "qdrant-vector-search" }, async () => {
  // Upsert vectors
  await client.upsert("example-collection", {
    points: [
      { id: 1, vector: [0.1, 0.2, 0.3], payload: { text: "recursion in programming" } },
      { id: 2, vector: [0.4, 0.5, 0.6], payload: { text: "data structures" } },
      { id: 3, vector: [0.7, 0.8, 0.9], payload: { text: "algorithm design" } },
    ],
  });
  console.log("Upserted 3 vectors");

  // Search vectors
  const searchResult = await client.search("example-collection", {
    vector: [0.1, 0.2, 0.3],
    limit: 2,
  });
  console.log("Search results:");
  for (const match of searchResult) {
    console.log(
      `  id=${match.id}: score=${match.score}, payload=${JSON.stringify(match.payload)}`
    );
  }
});

// ── 5. Flush and cleanup ──────────────────────────────────────────────
await respan.flush();
((globalThis as any).__qdrantServer as http.Server).close();
