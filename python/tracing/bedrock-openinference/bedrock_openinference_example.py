#!/usr/bin/env python3
"""
AWS Bedrock + OpenInference example for Respan tracing.

Uses openinference-instrumentation-bedrock to auto-instrument the boto3
Bedrock Runtime client and exports spans to Respan via respan-instrumentation-openinference.

Since we route LLM calls through the Respan gateway (OpenAI format),
a local HTTP proxy translates Bedrock Converse API requests to OpenAI format and back.
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

from openinference.instrumentation.bedrock import BedrockInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="bedrock-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

bedrock_oi = OpenInferenceInstrumentor(BedrockInstrumentor)
bedrock_oi.activate()


class BedrockConverseProxy(BaseHTTPRequestHandler):
    """Translates Bedrock Converse API requests to OpenAI chat completions.

    Botocore sends requests to paths like /model/{modelId}/converse.
    """

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        messages = []
        system_parts = body.get("system", [])
        if system_parts:
            sys_text = " ".join(p.get("text", "") for p in system_parts if "text" in p)
            if sys_text:
                messages.append({"role": "system", "content": sys_text})

        for msg in body.get("messages", []):
            role = msg.get("role", "user")
            content_parts = msg.get("content", [])
            text = " ".join(p.get("text", "") for p in content_parts if "text" in p)
            if text:
                messages.append({"role": role, "content": text})

        inference_config = body.get("inferenceConfig", {})
        openai_body = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": inference_config.get("temperature", 0),
            "max_tokens": inference_config.get("maxTokens", 256),
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
            self._send_json(resp.status_code, json.loads(resp.content))
            return

        openai_resp = resp.json()
        choice = openai_resp.get("choices", [{}])[0]
        usage = openai_resp.get("usage", {})

        bedrock_resp = {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": choice.get("message", {}).get("content", "")}],
                }
            },
            "stopReason": "end_turn",
            "usage": {
                "inputTokens": usage.get("prompt_tokens", 0),
                "outputTokens": usage.get("completion_tokens", 0),
                "totalTokens": usage.get("total_tokens", 0),
            },
            "metrics": {"latencyMs": 100},
        }

        self._send_json(200, bedrock_resp)

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_proxy():
    server = HTTPServer(("127.0.0.1", 0), BedrockConverseProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

import boto3

client = boto3.client(
    "bedrock-runtime",
    region_name="us-east-1",
    endpoint_url=proxy_url,
    aws_access_key_id="dummy",
    aws_secret_access_key="dummy",
)


@workflow(name="bedrock_openinference_workflow")
def bedrock_workflow(topic: str) -> str:
    response = client.converse(
        modelId="anthropic.claude-3-haiku-20240307-v1:0",
        messages=[
            {
                "role": "user",
                "content": [
                    {"text": f"Write a haiku about {topic}. Output ONLY the haiku."}
                ],
            }
        ],
        inferenceConfig={"temperature": 0, "maxTokens": 256},
    )

    output_message = response["output"]["message"]
    return output_message["content"][0]["text"]


def main() -> None:
    print("=" * 60)
    print("Bedrock OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = bedrock_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        bedrock_oi.deactivate()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
