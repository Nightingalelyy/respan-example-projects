#!/usr/bin/env python3
"""
OTLP Trace Ingest Demo

This script demonstrates how to send traces to Respan via the OTLP v2 endpoint,
which is the same format used by the respan-tracing SDK and OpenTelemetry exporters.

The sample trace simulates a customer support agent workflow with different span types:
- workflow: top-level pipeline orchestration
- agent: AI agent handling the conversation
- tool: function calls (order lookup, refund processing)
- chat: LLM inference calls with token usage
- task: utility operations (logging)

Files:
- trace_spans.json: Sample OTLP trace data with multiple span types
- utils.py: Processing utilities that shift timestamps and remap IDs
- main.py: This demo script

Usage:
    cd logs-to-trace-otlp/
    python3 main.py
"""

import os
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from utils import generate_trace_data
from pathlib import Path

load_dotenv(override=True)
parent_dir = Path(__file__).parent.resolve()
file_name = parent_dir / "trace_spans.json"

processed_payload = generate_trace_data(
    json.load(open(file_name)), datetime.now(timezone.utc)
)

trace_id = processed_payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["traceId"]

response = requests.post(
    f"{os.getenv('RESPAN_BASE_URL')}/v2/traces",
    json=processed_payload,
    headers={
        "Authorization": f"Bearer {os.getenv('RESPAN_API_KEY')}",
        "Content-Type": "application/json",
    },
)

print(f"Status: {response.status_code}, Response: {response.text}")
print(f"Trace ID: {trace_id}")
