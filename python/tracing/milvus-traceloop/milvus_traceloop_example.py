#!/usr/bin/env python3
"""
Milvus + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-milvus (Traceloop) to auto-instrument the
pymilvus SDK and exports spans to Respan.

Milvus Lite runs locally via a file-based database — no server needed.
The instrumentation wraps MilvusClient methods: create_collection, insert,
search, delete, query, get, upsert, hybrid_search.
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

from opentelemetry.instrumentation.milvus import MilvusInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="milvus-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

MilvusInstrumentor().instrument()

from pymilvus import MilvusClient


@workflow(name="milvus_traceloop_workflow")
def milvus_workflow() -> str:
    db_dir = tempfile.mkdtemp(prefix="milvus_example_")
    db_path = os.path.join(db_dir, "example.db")

    try:
        client = MilvusClient(uri=db_path)

        dim = 128
        client.create_collection(
            collection_name="documents",
            dimension=dim,
        )

        data = [
            {"id": i, "vector": np.random.randn(dim).tolist(), "text": f"document {i}"}
            for i in range(20)
        ]
        client.insert(collection_name="documents", data=data)

        query_vector = np.random.randn(dim).tolist()
        results = client.search(
            collection_name="documents",
            data=[query_vector],
            limit=5,
            output_fields=["text"],
        )

        client.delete(collection_name="documents", ids=[0, 1, 2])

        return f"Found {len(results[0])} results. Top match: id={results[0][0]['id']}"
    finally:
        shutil.rmtree(db_dir, ignore_errors=True)


def main() -> None:
    print("=" * 60)
    print("Milvus Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    result = milvus_workflow()
    print(result)

    telemetry.flush()


if __name__ == "__main__":
    main()
