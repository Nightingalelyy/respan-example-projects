#!/usr/bin/env python3
"""
AWS SageMaker Runtime + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-sagemaker (Traceloop) to auto-instrument the
boto3 SageMaker Runtime client and exports spans to Respan.

The SageMaker Runtime SDK sends POST requests to /endpoints/{name}/invocations.
A local HTTP proxy intercepts these, forwards the prompt to the Respan gateway
as an OpenAI chat completion, and returns a mock SageMaker response.
Dummy AWS credentials are used since calls never reach AWS.
"""
import json
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


class SageMakerToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates SageMaker invoke_endpoint requests to OpenAI chat completions."""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length) if content_length else b""

        if "/invocations" in self.path:
            self._handle_invoke(raw_body)
        else:
            self._send_response(200, b'{"status": "ok"}')

    def _handle_invoke(self, raw_body):
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, ValueError):
            body = {"inputs": raw_body.decode("utf-8", errors="replace")}

        prompt = ""
        if isinstance(body, dict):
            prompt = body.get("inputs", body.get("prompt", str(body)))
        elif isinstance(body, str):
            prompt = body

        openai_body = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 256,
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
            self._send_response(resp.status_code, resp.content)
            return

        openai_resp = resp.json()
        choice = openai_resp.get("choices", [{}])[0]
        generated_text = choice.get("message", {}).get("content", "")

        sagemaker_resp = [{"generated_text": generated_text}]

        payload = json.dumps(sagemaker_resp).encode()
        self._send_response(200, payload)

    def _send_response(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_proxy():
    server = HTTPServer(("127.0.0.1", 0), SageMakerToOpenAIProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

from opentelemetry.instrumentation.sagemaker import SageMakerInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="sagemaker-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

SageMakerInstrumentor().instrument()

import boto3

client = boto3.client(
    "sagemaker-runtime",
    region_name="us-east-1",
    endpoint_url=proxy_url,
    aws_access_key_id="dummy",
    aws_secret_access_key="dummy",
)


@workflow(name="sagemaker_traceloop_workflow")
def sagemaker_workflow(topic: str) -> str:
    payload = json.dumps({
        "inputs": f"Write a haiku about {topic}. Output ONLY the haiku.",
    })

    response = client.invoke_endpoint(
        EndpointName="my-llm-endpoint",
        ContentType="application/json",
        Body=payload,
    )

    result = json.loads(response["Body"].read())
    return result[0]["generated_text"]


def main() -> None:
    print("=" * 60)
    print("SageMaker Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = sagemaker_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
