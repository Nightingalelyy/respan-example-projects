/**
 * Pinecone — Vector DB operations with Respan tracing via Traceloop.
 *
 * Since we don't have real Pinecone credentials, a local HTTP mock server
 * simulates the Pinecone API (upsert + query). The SDK is pointed at it
 * via the index host parameter.
 *
 * The @traceloop/instrumentation-pinecone patches Index.prototype methods
 * (query, upsert, deleteOne, deleteMany, deleteAll) to create
 * Traceloop-format OTel spans.
 */

import "dotenv/config";
import http from "node:http";
import { trace } from "@opentelemetry/api";
import { PineconeInstrumentation } from "@traceloop/instrumentation-pinecone";
import * as PineconeModule from "@pinecone-database/pinecone";
import { Pinecone } from "@pinecone-database/pinecone";
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

// ── 2. Manually instrument @pinecone-database/pinecone ────────────────
const instrumentation = new PineconeInstrumentation();
instrumentation.setTracerProvider(trace.getTracerProvider());
instrumentation.manuallyInstrument(PineconeModule);

// ── 3. Local mock Pinecone server ─────────────────────────────────────
function startMockPinecone(): Promise<string> {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const chunks: Buffer[] = [];
      req.on("data", (c: Buffer) => chunks.push(c));
      req.on("end", () => {
        res.writeHead(200, { "Content-Type": "application/json" });

        if (req.url?.includes("/vectors/upsert")) {
          res.end(JSON.stringify({ upsertedCount: 3 }));
        } else if (req.url?.includes("/query")) {
          res.end(
            JSON.stringify({
              matches: [
                {
                  id: "vec1",
                  score: 0.97,
                  values: [0.1, 0.2, 0.3],
                  metadata: { topic: "recursion" },
                },
                {
                  id: "vec3",
                  score: 0.82,
                  values: [0.7, 0.8, 0.9],
                  metadata: { topic: "algorithms" },
                },
              ],
              namespace: "",
              usage: { readUnits: 1 },
            })
          );
        } else {
          res.end("{}");
        }
      });
    });

    server.listen(0, () => {
      const port = (server.address() as any).port;
      (globalThis as any).__pineconeServer = server;
      resolve(`http://localhost:${port}`);
    });
  });
}

const mockHost = await startMockPinecone();

// ── 4. Create Pinecone client pointing at mock server ─────────────────
const pc = new Pinecone({ apiKey: "mock-api-key" });
const index = pc.index("example-index", mockHost);

// Wrap in a Respan workflow so child spans pass through the filter
await respan.withWorkflow({ name: "pinecone-rag-workflow" }, async () => {
  // Upsert vectors
  await index.upsert({
    records: [
      { id: "vec1", values: [0.1, 0.2, 0.3] },
      { id: "vec2", values: [0.4, 0.5, 0.6] },
      { id: "vec3", values: [0.7, 0.8, 0.9] },
    ],
  });
  console.log("Upserted 3 vectors");

  // Query vectors
  const queryResult = await index.query({
    topK: 2,
    vector: [0.1, 0.2, 0.3],
    includeMetadata: true,
  });
  console.log("Query results:");
  for (const match of queryResult.matches) {
    console.log(`  ${match.id}: score=${match.score}, metadata=${JSON.stringify(match.metadata)}`);
  }
});

// ── 5. Flush and cleanup ──────────────────────────────────────────────
await respan.flush();
((globalThis as any).__pineconeServer as http.Server).close();
