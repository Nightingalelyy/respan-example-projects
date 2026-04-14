#!/usr/bin/env python3
"""
Vertex AI + OpenInference example for Respan tracing.

Uses openinference-instrumentation-vertexai to auto-instrument the
google-cloud-aiplatform (vertexai) SDK and exports spans to Respan.

Since we route LLM calls through the Respan gateway (OpenAI format),
a local HTTPS proxy translates Vertex AI REST requests to OpenAI format and back.
The Vertex AI SDK requires HTTPS even for custom endpoints.
"""
import json
import os
import re
import ssl
import subprocess
import tempfile
import threading
import warnings
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

from openinference.instrumentation.vertexai import VertexAIInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="vertexai-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

vertexai_oi = OpenInferenceInstrumentor(VertexAIInstrumentor)
vertexai_oi.activate()


class VertexAIToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates Vertex AI REST generateContent requests to OpenAI chat format."""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        model_match = re.search(r"models/([^:]+):generateContent", self.path)
        vertex_model = model_match.group(1) if model_match else "gemini-2.0-flash"

        messages = []
        system_instruction = body.get("systemInstruction")
        if system_instruction:
            parts = system_instruction.get("parts", [])
            sys_text = " ".join(p.get("text", "") for p in parts if "text" in p)
            if sys_text:
                messages.append({"role": "system", "content": sys_text})

        for content in body.get("contents", []):
            role = content.get("role", "user")
            role = "assistant" if role == "model" else role
            parts = content.get("parts", [])
            text = " ".join(p.get("text", "") for p in parts if "text" in p)
            if text:
                messages.append({"role": role, "content": text})

        gen_config = body.get("generationConfig", {})
        openai_body = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": gen_config.get("temperature", 0),
            "max_tokens": gen_config.get("maxOutputTokens", 256),
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
            self.send_response(resp.status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(resp.content)
            return

        openai_resp = resp.json()
        choice = openai_resp.get("choices", [{}])[0]
        usage = openai_resp.get("usage", {})

        vertex_resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": choice.get("message", {}).get("content", "")}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                    "index": 0,
                }
            ],
            "usageMetadata": {
                "promptTokenCount": usage.get("prompt_tokens", 0),
                "candidatesTokenCount": usage.get("completion_tokens", 0),
                "totalTokenCount": usage.get("total_tokens", 0),
            },
            "modelVersion": vertex_model,
        }

        payload = json.dumps(vertex_resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _generate_self_signed_cert():
    """Generate a self-signed cert and a combined CA bundle with system CAs."""
    cert_dir = tempfile.mkdtemp()
    cert_file = os.path.join(cert_dir, "cert.pem")
    key_file = os.path.join(cert_dir, "key.pem")
    combined_ca = os.path.join(cert_dir, "combined_ca.pem")
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", key_file, "-out", cert_file,
            "-days", "1", "-nodes",
            "-subj", "/CN=localhost",
            "-addext", "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )

    import certifi
    system_ca = certifi.where()
    with open(combined_ca, "w") as out:
        with open(system_ca) as f:
            out.write(f.read())
        out.write("\n")
        with open(cert_file) as f:
            out.write(f.read())

    return cert_file, key_file, combined_ca


def start_https_proxy():
    cert_file, key_file, combined_ca = _generate_self_signed_cert()

    server = HTTPServer(("127.0.0.1", 0), VertexAIToOpenAIProxy)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert_file, key_file)
    server.socket = ctx.wrap_socket(server.socket, server_side=True)

    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port, combined_ca


warnings.filterwarnings("ignore", category=DeprecationWarning)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

proxy_server, proxy_port, combined_ca_file = start_https_proxy()
proxy_host = f"127.0.0.1:{proxy_port}"

import google.auth.credentials as auth_creds


class _MockCredentials(auth_creds.Credentials):
    def __init__(self):
        super().__init__()
        self.token = "mock-token"

    def refresh(self, request):
        self.token = "mock-token"

    @property
    def valid(self):
        return True

    @property
    def expired(self):
        return False


os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["REQUESTS_CA_BUNDLE"] = combined_ca_file

import vertexai

vertexai.init(
    project="test-project",
    location="us-central1",
    credentials=_MockCredentials(),
    api_transport="rest",
    api_endpoint=proxy_host,
)

from vertexai.generative_models import GenerativeModel

model = GenerativeModel("gemini-2.0-flash")


@workflow(name="vertexai_openinference_workflow")
def vertexai_workflow(topic: str) -> str:
    response = model.generate_content(
        f"Write a haiku about {topic}. Output ONLY the haiku.",
        generation_config={"temperature": 0, "max_output_tokens": 256},
    )
    return response.text


def main() -> None:
    print("=" * 60)
    print("Vertex AI OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = vertexai_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        vertexai_oi.deactivate()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
