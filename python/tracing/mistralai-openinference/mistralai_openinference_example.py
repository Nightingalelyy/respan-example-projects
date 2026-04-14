#!/usr/bin/env python3
"""
MistralAI + OpenInference example for Respan tracing.

Uses openinference-instrumentation-mistralai to auto-instrument the MistralAI
Python SDK and exports spans to Respan via respan-instrumentation-openinference.

The MistralAI SDK sends requests to /v1/chat/completions. A lightweight local
proxy strips the /v1 prefix to match the Respan gateway's /chat/completions path.
"""
import os
import threading
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


class MistralPathProxy(BaseHTTPRequestHandler):
    """Strips /v1 prefix and forwards to Respan gateway."""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        path = self.path
        if path.startswith("/v1"):
            path = path[len("/v1"):]

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        resp = http_requests.post(
            f"{RESPAN_BASE_URL}{path}",
            data=body,
            headers={
                "Authorization": f"Bearer {RESPAN_API_KEY}",
                "Content-Type": "application/json",
            },
        )

        self.send_response(resp.status_code)
        for key, val in resp.headers.items():
            if key.lower() in ("content-type", "content-length"):
                self.send_header(key, val)
        self.end_headers()
        self.wfile.write(resp.content)


def start_proxy():
    server = HTTPServer(("127.0.0.1", 0), MistralPathProxy)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

from openinference.instrumentation.mistralai import MistralAIInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="mistralai-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

mistral_oi = OpenInferenceInstrumentor(MistralAIInstrumentor)
mistral_oi.activate()

from mistralai.client import Mistral

client = Mistral(
    api_key=RESPAN_API_KEY,
    server_url=proxy_url,
)


@workflow(name="mistralai_openinference_workflow")
def mistralai_workflow(topic: str) -> str:
    response = client.chat.complete(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": f"Write a haiku about {topic}. Output ONLY the haiku."},
        ],
        temperature=0,
        max_tokens=256,
    )
    return response.choices[0].message.content or ""


def main() -> None:
    print("=" * 60)
    print("MistralAI OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = mistralai_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        mistral_oi.deactivate()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
