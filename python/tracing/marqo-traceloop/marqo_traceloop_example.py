#!/usr/bin/env python3
"""
Marqo + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-marqo (Traceloop) to auto-instrument the
Marqo Python SDK and exports spans to Respan.

Marqo normally runs as a Docker container. This example uses a local HTTP
mock server that simulates Marqo's REST API for index creation, document
ingestion, search, and deletion.
"""
import json
import os
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")

MOCK_DOCUMENTS = {}


class MockMarqoServer(BaseHTTPRequestHandler):
    """Simulates Marqo REST API endpoints."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.strip("/")

        if path == "":
            self._send_json(200, {"message": "Welcome to Marqo", "version": "mock"})
        elif re.match(r"indexes/[^/]+/stats", path):
            self._send_json(200, {"numberOfDocuments": len(MOCK_DOCUMENTS), "numberOfVectors": len(MOCK_DOCUMENTS)})
        elif re.match(r"indexes/[^/]+", path):
            self._send_json(200, {"index_name": path.split("/")[1], "index_status": "READY"})
        elif path == "indexes":
            self._send_json(200, {"results": []})
        else:
            self._send_json(200, {})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length else b""
        body = json.loads(raw_body) if raw_body else {}

        parsed = urlparse(self.path)
        path = parsed.path.strip("/")

        if re.match(r"indexes/[^/]+/documents$", path):
            self._handle_add_documents(body)
        elif re.match(r"indexes/[^/]+/search$", path):
            self._handle_search(body)
        elif re.match(r"indexes/[^/]+/documents/delete-batch$", path):
            self._handle_delete(body)
        elif re.match(r"indexes/[^/]+$", path):
            self._handle_create_index(path, body)
        else:
            self._send_json(200, {"status": "ok"})

    def do_DELETE(self):
        self._send_json(200, {"acknowledged": True})

    def _handle_create_index(self, path, body):
        index_name = path.split("/")[1]
        self._send_json(200, {
            "acknowledged": True,
            "index": index_name,
        })

    def _handle_add_documents(self, body):
        documents = body if isinstance(body, list) else body.get("documents", [])
        items = []
        for doc in documents:
            doc_id = doc.get("_id", str(uuid.uuid4())[:8])
            MOCK_DOCUMENTS[doc_id] = doc
            items.append({"_id": doc_id, "result": "created", "status": 200})

        self._send_json(200, {
            "errors": False,
            "processingTimeMs": 50,
            "index_name": "test-index",
            "items": items,
        })

    def _handle_search(self, body):
        query = body.get("q", "")
        limit = body.get("limit", 5)

        hits = []
        for doc_id, doc in list(MOCK_DOCUMENTS.items())[:limit]:
            hit = dict(doc)
            hit["_id"] = doc_id
            hit["_score"] = 0.95
            hit["_highlights"] = [{"text": doc.get("text", "")}]
            hits.append(hit)

        self._send_json(200, {
            "hits": hits,
            "processingTimeMs": 10,
            "query": query,
            "limit": limit,
        })

    def _handle_delete(self, body):
        doc_ids = body if isinstance(body, list) else []
        items = []
        for doc_id in doc_ids:
            removed = MOCK_DOCUMENTS.pop(doc_id, None)
            items.append({
                "_id": doc_id,
                "result": "deleted" if removed else "not_found",
                "status": 200,
            })

        self._send_json(200, {
            "index_name": "test-index",
            "status": "succeeded",
            "type": "documentDeletion",
            "details": {"receivedDocumentIds": len(doc_ids), "deletedDocuments": len(items)},
            "items": items,
        })

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_mock_server():
    server = HTTPServer(("127.0.0.1", 0), MockMarqoServer)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


mock_server, mock_url = start_mock_server()

from opentelemetry.instrumentation.marqo import MarqoInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="marqo-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

MarqoInstrumentor().instrument()

import marqo

mq = marqo.Client(url=mock_url)


@workflow(name="marqo_traceloop_workflow")
def marqo_workflow() -> str:
    mq.create_index("test-index")

    mq.index("test-index").add_documents(
        [
            {"_id": "doc1", "text": "Recursion is a method where a function calls itself."},
            {"_id": "doc2", "text": "Iteration uses loops like for and while."},
            {"_id": "doc3", "text": "Dynamic programming breaks problems into subproblems."},
            {"_id": "doc4", "text": "Memoization caches results of expensive function calls."},
            {"_id": "doc5", "text": "A stack overflow occurs when recursion is too deep."},
        ],
        tensor_fields=["text"],
    )

    results = mq.index("test-index").search("What is recursion?")

    mq.index("test-index").delete_documents(ids=["doc4"])

    hits = results.get("hits", [])
    if hits:
        return f"Found {len(hits)} results. Top match: {hits[0].get('text', 'N/A')}"
    return "No results found."


def main() -> None:
    print("=" * 60)
    print("Marqo Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = marqo_workflow()
        print(result)
    finally:
        telemetry.flush()
        mock_server.shutdown()


if __name__ == "__main__":
    main()
