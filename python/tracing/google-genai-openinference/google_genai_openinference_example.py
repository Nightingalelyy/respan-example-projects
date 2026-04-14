#!/usr/bin/env python3
"""
Google GenAI + OpenInference example for Respan tracing.

Uses openinference-instrumentation-google-genai to auto-instrument the
google-genai SDK and exports spans to Respan.

Since we route LLM calls through the Respan gateway (OpenAI format),
a local HTTP proxy translates Google GenAI requests to OpenAI format and back.
"""
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")
RESPAN_BASE_URL = (
    os.getenv("RESPAN_GATEWAY_BASE_URL")
    or os.getenv("RESPAN_BASE_URL")
    or "https://api.respan.ai/api"
).rstrip("/")

from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
from respan_instrumentation_openinference import OpenInferenceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="google-genai-openinference-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

genai_oi = OpenInferenceInstrumentor(GoogleGenAIInstrumentor)
genai_oi.activate()


class GeminiToOpenAIProxy(BaseHTTPRequestHandler):
    """Translates Google GenAI requests to OpenAI chat completion format."""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}

        model_match = re.search(r"models/([^:]+):generateContent", self.path)
        gemini_model = model_match.group(1) if model_match else "gemini-2.0-flash"

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

        resp = requests.post(
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

        gemini_resp = {
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
            "modelVersion": gemini_model,
        }

        payload = json.dumps(gemini_resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start_proxy() -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), GeminiToOpenAIProxy)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


proxy_server, proxy_url = start_proxy()

from google import genai

client = genai.Client(
    api_key="proxy-passthrough",
    http_options={"base_url": proxy_url, "api_version": "v1beta"},
)


@workflow(name="google_genai_openinference_workflow")
def genai_workflow(topic: str) -> str:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"Write a haiku about {topic}. Output ONLY the haiku.",
    )
    return response.text or ""


def main() -> None:
    print("=" * 60)
    print("Google GenAI OpenInference Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    try:
        result = genai_workflow(topic="recursion in programming")
        print(result)
    finally:
        telemetry.flush()
        genai_oi.deactivate()
        proxy_server.shutdown()


if __name__ == "__main__":
    main()
