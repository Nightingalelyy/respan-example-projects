#!/usr/bin/env python3
"""
Weaviate + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-weaviate (Traceloop) to auto-instrument the
Weaviate Python SDK (v3) and exports spans to Respan.

Weaviate normally runs as a server. A local HTTP mock simulates the Weaviate
v1 REST API endpoints: /v1/meta, /v1/schema, /v1/objects, /v1/graphql.
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

MOCK_CLASSES = {}
MOCK_OBJECTS = {}


class MockWeaviateServer(BaseHTTPRequestHandler):
    """Simulates Weaviate v1 REST API."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/")

        if path in ("/v1/meta", "/v1/.well-known/ready"):
            self._send_json(200, {
                "hostname": "http://localhost",
                "version": "1.24.0-mock",
                "modules": {},
            })
        elif path == "/v1/schema":
            self._send_json(200, {"classes": list(MOCK_CLASSES.values())})
        elif re.match(r"/v1/schema/\w+$", path):
            class_name = path.split("/")[-1]
            cls = MOCK_CLASSES.get(class_name)
            if cls:
                self._send_json(200, cls)
            else:
                self._send_json(404, {"error": [{"message": f"class {class_name} not found"}]})
        elif path == "/v1/objects":
            self._send_json(200, {"objects": list(MOCK_OBJECTS.values())})
        elif re.match(r"/v1/objects/[\w-]+$", path):
            obj_id = path.split("/")[-1]
            obj = MOCK_OBJECTS.get(obj_id)
            if obj:
                self._send_json(200, obj)
            else:
                self._send_json(404, {"error": [{"message": "not found"}]})
        elif path in ("/v1/.well-known/openid-configuration",):
            self._send_json(404, {})
        else:
            self._send_json(200, {})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(content_length) if content_length else b""
        body = json.loads(raw) if raw else {}

        path = urlparse(self.path).path.rstrip("/")

        if path == "/v1/schema":
            self._handle_create_class(body)
        elif path == "/v1/objects":
            self._handle_create_object(body)
        elif path == "/v1/graphql":
            self._handle_graphql(body)
        elif path == "/v1/batch/objects":
            self._handle_batch_objects(body)
        else:
            self._send_json(200, {})

    def do_DELETE(self):
        path = urlparse(self.path).path.rstrip("/")
        if re.match(r"/v1/schema/\w+$", path):
            class_name = path.split("/")[-1]
            MOCK_CLASSES.pop(class_name, None)
            self._send_json(200, {})
        else:
            self._send_json(200, {})

    def _handle_create_class(self, body):
        class_name = body.get("class", "Unknown")
        MOCK_CLASSES[class_name] = body
        self._send_json(200, body)

    def _handle_create_object(self, body):
        obj_id = body.get("id", str(uuid.uuid4()))
        obj = {
            "id": obj_id,
            "class": body.get("class", ""),
            "properties": body.get("properties", {}),
            "vector": body.get("vector", []),
            "creationTimeUnix": 1700000000000,
            "lastUpdateTimeUnix": 1700000000000,
        }
        MOCK_OBJECTS[obj_id] = obj
        self._send_json(200, obj)

    def _handle_batch_objects(self, body):
        objects = body.get("objects", [])
        results = []
        for obj_data in objects:
            obj_id = obj_data.get("id", str(uuid.uuid4()))
            obj = {
                "id": obj_id,
                "class": obj_data.get("class", ""),
                "properties": obj_data.get("properties", {}),
                "vector": obj_data.get("vector", []),
            }
            MOCK_OBJECTS[obj_id] = obj
            results.append({"id": obj_id, "result": {"status": "SUCCESS"}})
        self._send_json(200, results)

    def _handle_graphql(self, body):
        query = body.get("query", "")

        objects_list = list(MOCK_OBJECTS.values())[:5]
        class_name = "Document"
        for cls in MOCK_CLASSES:
            class_name = cls
            break

        results = []
        for obj in objects_list:
            entry = dict(obj.get("properties", {}))
            entry["_additional"] = {
                "id": obj.get("id", ""),
                "certainty": 0.95,
                "distance": 0.05,
            }
            results.append(entry)

        if "Aggregate" in query:
            self._send_json(200, {
                "data": {
                    "Aggregate": {
                        class_name: [{"meta": {"count": len(MOCK_OBJECTS)}}]
                    }
                }
            })
        else:
            self._send_json(200, {
                "data": {
                    "Get": {
                        class_name: results
                    }
                }
            })

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_mock_server():
    server = HTTPServer(("127.0.0.1", 0), MockWeaviateServer)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


mock_server, mock_port = start_mock_server()
mock_url = f"http://127.0.0.1:{mock_port}"

from opentelemetry.instrumentation.weaviate import WeaviateInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="weaviate-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

WeaviateInstrumentor().instrument()

import weaviate

client = weaviate.Client(url=mock_url)


@workflow(name="weaviate_traceloop_workflow")
def weaviate_workflow() -> str:
    class_obj = {
        "class": "Document",
        "description": "A collection of text documents",
        "properties": [
            {"name": "text", "dataType": ["text"], "description": "Document text"},
            {"name": "category", "dataType": ["text"], "description": "Document category"},
        ],
    }
    client.schema.create_class(class_obj)

    schema = client.schema.get()

    for i in range(5):
        client.data_object.create(
            data_object={"text": f"Document {i} about recursion", "category": f"cat-{i % 3}"},
            class_name="Document",
        )

    result = (
        client.query
        .get("Document", ["text", "category"])
        .with_limit(5)
        .do()
    )

    docs = result.get("data", {}).get("Get", {}).get("Document", [])
    client.schema.delete_class("Document")

    return f"Found {len(docs)} documents. Schema had {len(schema.get('classes', []))} class(es)."


def main() -> None:
    print("=" * 60)
    print("Weaviate Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = weaviate_workflow()
        print(result)
    finally:
        telemetry.flush()
        mock_server.shutdown()


if __name__ == "__main__":
    main()
