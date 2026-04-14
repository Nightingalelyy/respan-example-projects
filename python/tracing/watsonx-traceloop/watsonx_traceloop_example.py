#!/usr/bin/env python3
"""
IBM WatsonX + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-watsonx (Traceloop) to auto-instrument the
IBM watsonx.ai Python SDK and exports spans to Respan.

Since we route LLM calls through the Respan gateway (OpenAI format),
a local HTTPS proxy translates WatsonX text generation requests to OpenAI chat
completions format and converts responses back.
The WatsonX SDK requires HTTPS, so a self-signed certificate is used.
A mock token skips real IAM authentication.
"""
import json
import os
import ssl
import subprocess
import tempfile
import threading
import warnings
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

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


class WatsonxToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates WatsonX API requests to OpenAI chat completions."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if "/v2/projects/" in parsed.path:
            self._send_json(200, {
                "entity": {
                    "name": "mock-project",
                    "storage": {"type": "bmcos_object_storage", "guid": "mock-guid"},
                },
                "metadata": {"guid": "mock-project-id"},
            })
        elif "/ml/v1/foundation_model_specs" in parsed.path:
            self._send_json(200, {
                "resources": [{
                    "model_id": "ibm/granite-3-2-8b-instruct",
                    "label": "granite-3-2-8b-instruct",
                    "provider": "IBM",
                    "task_ids": ["generation"],
                }],
                "total_count": 1,
            })
        elif "/v2/asset_types" in parsed.path:
            self._send_json(200, {"resources": []})
        else:
            self._send_json(200, {"resources": [], "total_count": 0})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}
        parsed = urlparse(self.path)

        if "/ml/v1/text/generation" in parsed.path:
            self._handle_generate(body)
        elif "/identity/token" in parsed.path:
            self._send_json(200, {
                "access_token": "mock-access-token",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expiration": 9999999999,
            })
        else:
            self._send_json(200, {"status": "ok"})

    def _handle_generate(self, body):
        prompt = body.get("input", "")
        model_id = body.get("model_id", "ibm/granite-3-2-8b-instruct")
        params = body.get("parameters", {})

        openai_body = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": params.get("temperature", 0),
            "max_tokens": params.get("max_new_tokens", 256),
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

        watsonx_resp = {
            "model_id": model_id,
            "model_version": "1.0.0",
            "created_at": str(openai_resp.get("created", "")),
            "results": [{
                "generated_text": choice.get("message", {}).get("content", ""),
                "generated_token_count": usage.get("completion_tokens", 0),
                "input_token_count": usage.get("prompt_tokens", 0),
                "stop_reason": "eos_token",
            }],
        }

        self._send_json(200, watsonx_resp)

    def _send_json(self, status, data):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def _generate_self_signed_cert():
    """Generate a self-signed cert and a combined CA bundle."""
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

    server = HTTPServer(("127.0.0.1", 0), WatsonxToOpenAIProxy)
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
proxy_host = f"https://127.0.0.1:{proxy_port}"

os.environ["REQUESTS_CA_BUNDLE"] = combined_ca_file
os.environ["SSL_CERT_FILE"] = combined_ca_file

from opentelemetry.instrumentation.watsonx import WatsonxInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="watsonx-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

WatsonxInstrumentor().instrument(skip_dep_check=True)

from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

credentials = Credentials(
    url=proxy_host,
    token="mock-bearer-token",
    instance_id="openid",
    version="5.0",
)

model = ModelInference(
    model_id="ibm/granite-3-2-8b-instruct",
    params={"max_new_tokens": 256, "temperature": 0},
    credentials=credentials,
    project_id="mock-project-id",
)


@workflow(name="watsonx_traceloop_workflow")
def watsonx_workflow(topic: str) -> str:
    response = model.generate(
        prompt=f"Write a haiku about {topic}. Output ONLY the haiku."
    )
    return response["results"][0]["generated_text"]


def main() -> None:
    print("=" * 60)
    print("WatsonX Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = watsonx_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
