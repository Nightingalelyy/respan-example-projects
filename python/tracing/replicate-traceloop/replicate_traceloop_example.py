#!/usr/bin/env python3
"""
Replicate + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-replicate (Traceloop) to auto-instrument the
Replicate Python SDK and exports spans to Respan.

The Replicate SDK creates predictions via POST /v1/models/{owner}/{name}/predictions.
A local HTTP proxy intercepts these requests, forwards the prompt to the Respan
gateway as an OpenAI chat completion, and returns a mock Replicate prediction response.
"""
import json
import os
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests as http_requests
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")


class ReplicateToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates Replicate prediction requests to OpenAI chat completions."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        self._send_json(200, {})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        model_match = re.search(r"/v1/models/([^/]+/[^/]+)/predictions", self.path)
        if model_match or "/v1/predictions" in self.path:
            self._handle_prediction(body, model_match)
        else:
            self._send_json(200, {"status": "ok"})

    def _handle_prediction(self, body, model_match):
        model_ref = model_match.group(1) if model_match else "meta/llama-3-8b-instruct"
        input_data = body.get("input", {})
        prompt = input_data.get("prompt", "")

        messages = []
        system_prompt = input_data.get("system_prompt", "")
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        openai_body = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": input_data.get("temperature", 0),
            "max_tokens": input_data.get("max_tokens", 256),
        }

        resp = http_requests.post(
            f"{RESPAN_BASE_URL}/chat/completions",
            json=openai_body,
            headers={
                "Authorization": f"Bearer {RESPAN_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        if resp.status_code != 200:
            prediction_id = str(uuid.uuid4())[:8]
            self._send_json(200, {
                "id": prediction_id,
                "model": model_ref,
                "version": "mock-version",
                "status": "failed",
                "input": input_data,
                "output": None,
                "error": resp.text,
                "metrics": {},
                "created_at": "2026-01-01T00:00:00Z",
            })
            return

        openai_resp = resp.json()
        choice = openai_resp.get("choices", [{}])[0]
        usage = openai_resp.get("usage", {})
        generated_text = choice.get("message", {}).get("content", "")

        prediction_id = str(uuid.uuid4())[:8]
        prediction_resp = {
            "id": prediction_id,
            "model": model_ref,
            "version": "mock-version",
            "status": "succeeded",
            "input": input_data,
            "output": generated_text,
            "error": None,
            "logs": "",
            "metrics": {
                "predict_time": 1.0,
                "input_token_count": usage.get("prompt_tokens", 0),
                "output_token_count": usage.get("completion_tokens", 0),
            },
            "created_at": "2026-01-01T00:00:00Z",
            "started_at": "2026-01-01T00:00:01Z",
            "completed_at": "2026-01-01T00:00:02Z",
            "urls": {
                "get": f"http://localhost/v1/predictions/{prediction_id}",
                "cancel": f"http://localhost/v1/predictions/{prediction_id}/cancel",
            },
        }

        self._send_json(200, prediction_resp)

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_proxy():
    server = HTTPServer(("127.0.0.1", 0), ReplicateToOpenAIProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

from opentelemetry.instrumentation.replicate import ReplicateInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="replicate-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

ReplicateInstrumentor().instrument()

import replicate

replicate.default_client._api_token = "proxy-passthrough"
replicate.default_client._base_url = proxy_url


@workflow(name="replicate_traceloop_workflow")
def replicate_workflow(topic: str) -> str:
    output = replicate.run(
        "meta/llama-3-8b-instruct",
        input={
            "prompt": f"Write a haiku about {topic}. Output ONLY the haiku.",
            "temperature": 0,
            "max_tokens": 256,
        },
    )
    if isinstance(output, str):
        return output
    return "".join(str(chunk) for chunk in output)


def main() -> None:
    print("=" * 60)
    print("Replicate Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = replicate_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
