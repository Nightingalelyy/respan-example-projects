#!/usr/bin/env python3
"""
Pinecone + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-pinecone (Traceloop) to auto-instrument the
Pinecone Python SDK and exports spans to Respan.

Pinecone is a cloud vector database. A local HTTP mock server simulates the
Pinecone data plane REST API endpoints (/vectors/upsert, /query, /vectors/delete)
so no real Pinecone account is needed.
"""
import json
import os
import random
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")

MOCK_VECTORS = {}


class MockPineconeServer(BaseHTTPRequestHandler):
    """Simulates Pinecone data plane REST API."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = self.path.split("?")[0].strip("/")
        if path == "describe_index_stats":
            self._send_json(200, {
                "namespaces": {"": {"vectorCount": len(MOCK_VECTORS)}},
                "dimension": 128,
                "indexFullness": 0.0,
                "totalVectorCount": len(MOCK_VECTORS),
            })
        else:
            self._send_json(200, {})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length) if content_length else b""
        body = json.loads(raw) if raw else {}

        path = self.path.split("?")[0].strip("/")

        if path == "vectors/upsert":
            self._handle_upsert(body)
        elif path == "query":
            self._handle_query(body)
        elif path == "vectors/delete":
            self._handle_delete(body)
        else:
            self._send_json(200, {})

    def _handle_upsert(self, body):
        vectors = body.get("vectors", [])
        for vec in vectors:
            vid = vec.get("id", str(uuid.uuid4())[:8])
            MOCK_VECTORS[vid] = {
                "values": vec.get("values", []),
                "metadata": vec.get("metadata", {}),
            }
        self._send_json(200, {"upsertedCount": len(vectors)})

    def _handle_query(self, body):
        top_k = body.get("topK", 5)
        include_values = body.get("includeValues", False)
        include_metadata = body.get("includeMetadata", False)
        namespace = body.get("namespace", "")

        matches = []
        for vid, data in list(MOCK_VECTORS.items())[:top_k]:
            match = {
                "id": vid,
                "score": round(random.uniform(0.7, 0.99), 4),
            }
            if include_values:
                match["values"] = data["values"]
            if include_metadata:
                match["metadata"] = data["metadata"]
            matches.append(match)

        matches.sort(key=lambda m: m["score"], reverse=True)

        self._send_json(200, {
            "matches": matches,
            "namespace": namespace,
            "usage": {"readUnits": 5},
        })

    def _handle_delete(self, body):
        ids = body.get("ids", [])
        for vid in ids:
            MOCK_VECTORS.pop(vid, None)
        self._send_json(200, {})

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_mock_server():
    server = HTTPServer(("127.0.0.1", 0), MockPineconeServer)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


mock_server, mock_port = start_mock_server()

from opentelemetry.instrumentation.pinecone import PineconeInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="pinecone-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

PineconeInstrumentor().instrument()

from pinecone import Pinecone

pc = Pinecone(api_key="mock-api-key")
index = pc.Index(
    name="test-index",
    host=f"http://localhost:{mock_port}",
)


@workflow(name="pinecone_traceloop_workflow")
def pinecone_workflow() -> str:
    dim = 128
    vectors = [
        {
            "id": f"vec-{i}",
            "values": [random.random() for _ in range(dim)],
            "metadata": {"category": f"cat-{i % 3}", "text": f"document {i}"},
        }
        for i in range(10)
    ]
    index.upsert(vectors=vectors)

    query_vector = [random.random() for _ in range(dim)]
    results = index.query(
        vector=query_vector,
        top_k=5,
        include_metadata=True,
    )

    index.delete(ids=["vec-0", "vec-1", "vec-2"])

    matches = results.get("matches", [])
    if matches:
        return f"Found {len(matches)} matches. Top: {matches[0]['id']} (score={matches[0]['score']})"
    return "No matches found."


def main() -> None:
    print("=" * 60)
    print("Pinecone Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = pinecone_workflow()
        print(result)
    finally:
        telemetry.flush()
        mock_server.shutdown()


if __name__ == "__main__":
    main()
