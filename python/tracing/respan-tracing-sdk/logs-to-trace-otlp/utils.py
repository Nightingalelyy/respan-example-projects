"""
OTLP Trace Processing Utilities

This module provides utilities for preprocessing OTLP trace data to create new unique
traces while preserving exact relationships and timing between spans.

Key Functions:
- generate_trace_data(): Main function to remap IDs and shift timestamps in OTLP payloads
"""

import hashlib
import copy
from datetime import datetime, timezone
from typing import Dict, Any


def _deterministic_hex_mapper(original: str, seed: str) -> str:
    """Map a hex string to a new hex string of the same length deterministically."""
    combined = f"{seed}:{original}"
    hex_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()
    result = hex_hash
    counter = 0
    while len(result) < len(original):
        counter += 1
        result += hashlib.sha256(
            f"{combined}:{counter}".encode("utf-8")
        ).hexdigest()
    return result[: len(original)]


def generate_trace_data(
    otlp_payload: Dict[str, Any], run_timestamp: datetime
) -> Dict[str, Any]:
    """
    Generate new OTLP trace data from existing payload while preserving all relationships.

    Remaps traceId, spanId, and parentSpanId consistently and shifts all timestamps
    to be anchored at run_timestamp.

    Args:
        otlp_payload: OTLP ExportTraceServiceRequest dict with resourceSpans
        run_timestamp: Timestamp used for seed generation and time anchoring

    Returns:
        Processed OTLP payload with new IDs and shifted timestamps
    """
    payload = copy.deepcopy(otlp_payload)
    seed = run_timestamp.isoformat()

    # Find the earliest timestamp across all spans for anchoring
    earliest_ns = None
    for rs in payload.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for span in ss.get("spans", []):
                start_ns = int(span.get("startTimeUnixNano", "0"))
                if start_ns > 0 and (earliest_ns is None or start_ns < earliest_ns):
                    earliest_ns = start_ns

    anchor_ns = int(run_timestamp.timestamp() * 1_000_000_000)

    for rs in payload.get("resourceSpans", []):
        for ss in rs.get("scopeSpans", []):
            for span in ss.get("spans", []):
                # Remap trace ID
                if "traceId" in span:
                    span["traceId"] = _deterministic_hex_mapper(
                        span["traceId"], seed
                    )

                # Remap span ID
                if "spanId" in span:
                    span["spanId"] = _deterministic_hex_mapper(
                        span["spanId"], seed
                    )

                # Remap parent span ID
                if "parentSpanId" in span and span["parentSpanId"]:
                    span["parentSpanId"] = _deterministic_hex_mapper(
                        span["parentSpanId"], seed
                    )

                # Shift timestamps
                if earliest_ns is not None:
                    if "startTimeUnixNano" in span:
                        offset = int(span["startTimeUnixNano"]) - earliest_ns
                        span["startTimeUnixNano"] = str(anchor_ns + offset)

                    if "endTimeUnixNano" in span:
                        offset = int(span["endTimeUnixNano"]) - earliest_ns
                        span["endTimeUnixNano"] = str(anchor_ns + offset)

    return payload
