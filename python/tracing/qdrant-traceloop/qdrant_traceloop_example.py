#!/usr/bin/env python3
"""
Qdrant + Traceloop instrumentation example for Respan tracing.

Uses opentelemetry-instrumentation-qdrant (Traceloop) to auto-instrument the
qdrant-client Python SDK and exports spans to Respan.

Qdrant supports an in-memory mode — no server needed. The instrumentation wraps
QdrantClient methods: upsert, search, query_points, delete, scroll, and more.
"""
import os
import random
from pathlib import Path

from dotenv import load_dotenv

ROOT_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(ROOT_ENV_PATH, override=True)

RESPAN_API_KEY = os.getenv("RESPAN_GATEWAY_API_KEY") or os.getenv("RESPAN_API_KEY")

from opentelemetry.instrumentation.qdrant import QdrantInstrumentor
from respan_tracing import RespanTelemetry
from respan_tracing.decorators import workflow

telemetry = RespanTelemetry(
    app_name="qdrant-traceloop-example",
    api_key=RESPAN_API_KEY,
    is_batching_enabled=False,
    instruments=set(),
)

QdrantInstrumentor().instrument()

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointIdsList, PointStruct, VectorParams


@workflow(name="qdrant_traceloop_workflow")
def qdrant_workflow() -> str:
    client = QdrantClient(":memory:")

    dim = 128
    client.create_collection(
        collection_name="documents",
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    points = [
        PointStruct(
            id=i,
            vector=[random.random() for _ in range(dim)],
            payload={"text": f"document {i}", "category": f"cat-{i % 3}"},
        )
        for i in range(20)
    ]
    client.upsert(collection_name="documents", points=points)

    query_vector = [random.random() for _ in range(dim)]
    results = client.query_points(
        collection_name="documents",
        query=query_vector,
        limit=5,
    )

    client.delete(
        collection_name="documents",
        points_selector=PointIdsList(points=[0, 1, 2]),
    )

    hits = results.points
    if hits:
        top = hits[0]
        return f"Found {len(hits)} results. Top: id={top.id} (score={top.score:.4f})"
    return "No results found."


def main() -> None:
    print("=" * 60)
    print("Qdrant Traceloop Example")
    print("=" * 60)

    if not RESPAN_API_KEY:
        print("Skipping: RESPAN_API_KEY not set.")
        return

    result = qdrant_workflow()
    print(result)

    telemetry.flush()


if __name__ == "__main__":
    main()
