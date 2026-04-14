#!/usr/bin/env python3
"""
Ollama + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-ollama (Traceloop) to auto-instrument the
Ollama Python SDK and exports spans to Respan.

Since we route LLM calls through the Respan gateway (OpenAI format),
a local HTTP proxy translates Ollama /api/chat requests to OpenAI chat
completions format and converts responses back.
"""
import json
import os
import threading
from datetime import datetime, timezone
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


class OllamaToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates Ollama /api/chat requests to OpenAI chat completions."""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        if "/api/chat" in self.path:
            self._handle_chat(body)
        else:
            self._send_json(404, {"error": f"Unknown path: {self.path}"})

    def _handle_chat(self, body):
        messages = []
        for msg in body.get("messages", []):
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

        options = body.get("options", {})
        openai_body = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": options.get("temperature", 0),
            "max_tokens": options.get("num_predict", 256),
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
            self._send_json(resp.status_code, resp.json())
            return

        openai_resp = resp.json()
        choice = openai_resp.get("choices", [{}])[0]
        usage = openai_resp.get("usage", {})

        created_ts = openai_resp.get("created", 0)
        created_iso = datetime.fromtimestamp(created_ts, tz=timezone.utc).isoformat()

        ollama_resp = {
            "model": body.get("model", "gpt-4o-mini"),
            "created_at": created_iso,
            "message": {
                "role": "assistant",
                "content": choice.get("message", {}).get("content", ""),
            },
            "done": True,
            "done_reason": "stop",
            "total_duration": 1000000000,
            "load_duration": 0,
            "prompt_eval_count": usage.get("prompt_tokens", 0),
            "prompt_eval_duration": 500000000,
            "eval_count": usage.get("completion_tokens", 0),
            "eval_duration": 500000000,
        }

        self._send_json(200, ollama_resp)

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_proxy():
    server = HTTPServer(("127.0.0.1", 0), OllamaToOpenAIProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

from opentelemetry.instrumentation.ollama import OllamaInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="ollama-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

OllamaInstrumentor().instrument()

from ollama import Client

client = Client(host=proxy_url)


@workflow(name="ollama_traceloop_workflow")
def ollama_workflow(topic: str) -> str:
    response = client.chat(
        model="llama3.2",
        messages=[
            {"role": "user", "content": f"Write a haiku about {topic}. Output ONLY the haiku."},
        ],
        options={"temperature": 0, "num_predict": 256},
    )
    return response.message.content or ""


def main() -> None:
    print("=" * 60)
    print("Ollama Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = ollama_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
