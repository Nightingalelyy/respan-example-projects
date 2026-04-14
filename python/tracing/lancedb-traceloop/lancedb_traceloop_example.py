#!/usr/bin/env python3
"""
LanceDB + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-lancedb (Traceloop) to auto-instrument the
LanceDB Python SDK and exports spans to Respan.

LanceDB is a local vector database — no API proxy is needed. This example
creates a table, adds vector data, performs a similarity search, and deletes
a record, all of which are traced.
"""
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")

from opentelemetry.instrumentation.lancedb import LanceInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="lancedb-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

LanceInstrumentor().instrument()

import lancedb


@workflow(name="lancedb_traceloop_workflow")
def lancedb_workflow() -> str:
    db_path = tempfile.mkdtemp(prefix="lancedb_example_")

    try:
        db = lancedb.connect(db_path)

        dim = 128
        data = [
            {"id": i, "text": f"document {i}", "vector": np.random.randn(dim).tolist()}
            for i in range(20)
        ]

        table = db.create_table("documents", data=data)

        extra_data = [
            {"id": 100 + i, "text": f"extra doc {i}", "vector": np.random.randn(dim).tolist()}
            for i in range(5)
        ]
        table.add(extra_data)

        query_vector = np.random.randn(dim).tolist()
        results = table.search(query_vector).limit(5).to_list()

        table.delete('id = 100')

        return f"Found {len(results)} results. Top match: {results[0]['text']}"
    finally:
        shutil.rmtree(db_path, ignore_errors=True)


def main() -> None:
    print("=" * 60)
    print("LanceDB Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    result = lancedb_workflow()
    print(result)

    telemetry.flush()


if __name__ == "__main__":
    main()
