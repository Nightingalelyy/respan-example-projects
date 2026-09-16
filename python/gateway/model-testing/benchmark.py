"""Repeatable streaming TTFT, throughput, and latency measurements via Respan."""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from catalog import CatalogError, discover_models
from run import redact

HERE = Path(__file__).resolve().parent
DEFAULT_MODELS = ["prism/deepseek-v4-flash", "prism/deepseek-v4.1-flash"]
FIELDS = ["model", "phase", "sample", "status", "http_status", "ttft_ms", "latency_ms",
          "output_tokens_per_second", "prompt_tokens", "completion_tokens", "reasoning_tokens",
          "finish_reason", "response_model", "stream_end", "log_id", "request_id", "custom_identifier", "error"]


def sse_events(lines):
    data = []
    for line in lines:
        if not line:
            if data:
                yield "\n".join(data)
                data = []
        elif line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
    if data:
        yield "\n".join(data)


def token_count(value, field):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def measure(client, base_url, model, prompt, max_tokens, run_id, phase, sample, clock=perf_counter):
    """One request; no retries. Keep failed attempts and unavailable metrics."""
    row = dict.fromkeys(FIELDS)
    row.update(model=model["id"], phase=phase, sample=sample, status="error", error="",
               custom_identifier=f"{run_id}:{uuid4().hex[:12]}")
    token_field = "max_completion_tokens" if model.get("reasoning_support") else "max_tokens"
    payload = {"model": model["id"], "messages": [{"role": "user", "content": prompt}],
               token_field: max_tokens, "temperature": 0, "stream": True,
               "stream_options": {"include_usage": True}, "cache_enabled": False,
               "disable_fallback": True, "retry_params": {"retry_enabled": False},
               "custom_identifier": row["custom_identifier"],
               "metadata": {"benchmark_run": run_id, "benchmark_phase": phase,
                            "benchmark_sample": sample, "benchmark_model": model["id"]}}
    first_token = None
    started = clock()
    try:
        with client.stream("POST", base_url + "/chat/completions", json=payload) as response:
            row.update(http_status=response.status_code, log_id=response.headers.get("x-respan-log-id"),
                       request_id=response.headers.get("x-respan-gateway-request-id"))
            if not response.is_success:
                response.read()
                raise ValueError(f"HTTP {response.status_code}: {response.text[:1500]}")
            if "text/event-stream" not in response.headers.get("content-type", ""):
                raise ValueError("Expected a text/event-stream response")
            row["stream_end"] = "eof"
            for event in sse_events(response.iter_lines()):
                if event.strip() == "[DONE]":
                    row["stream_end"] = "done"
                    break
                chunk = json.loads(event)
                if not isinstance(chunk, dict):
                    raise ValueError("Stream chunk must be an object")
                if chunk.get("error"):
                    raise ValueError(f"Stream error: {str(chunk['error'])[:1500]}")
                row["response_model"] = chunk.get("model") or row["response_model"]
                usage = chunk.get("usage")
                if usage is not None:
                    if not isinstance(usage, dict):
                        raise ValueError("Stream usage must be an object")
                    for field in ("prompt_tokens", "completion_tokens"):
                        if usage.get(field) is not None:
                            row[field] = token_count(usage[field], field)
                    details = usage.get("completion_tokens_details") or {}
                    if not isinstance(details, dict):
                        raise ValueError("Completion token details must be an object")
                    if details.get("reasoning_tokens") is not None:
                        row["reasoning_tokens"] = token_count(details["reasoning_tokens"], "reasoning_tokens")
                choices = chunk.get("choices", [])
                if not isinstance(choices, list):
                    raise ValueError("Stream choices must be an array")
                for choice in choices:
                    if not isinstance(choice, dict) or choice.get("index", 0) != 0:
                        raise ValueError("Expected only choice index 0")
                    delta = choice.get("delta")
                    if delta is None:
                        delta = {}
                    if not isinstance(delta, dict):
                        raise ValueError("Stream delta must be an object")
                    for field in ("content", "reasoning_content", "reasoning"):
                        value = delta.get(field)
                        if value is not None and not isinstance(value, str):
                            raise ValueError(f"Stream {field} must be text")
                        if value and first_token is None:
                            first_token = clock()
                    finish = choice.get("finish_reason")
                    if finish is not None:
                        if finish not in ("stop", "length"):
                            raise ValueError(f"Unexpected finish_reason: {finish!r}")
                        row["finish_reason"] = finish
            ended = clock()
        elapsed = ended - started
        row["latency_ms"] = elapsed * 1000
        if first_token is not None:
            row["ttft_ms"] = (first_token - started) * 1000
        if not row["finish_reason"]:
            raise ValueError("Truncated stream: missing terminal finish_reason")
        if first_token is None:
            raise ValueError("Stream contained no generated text or reasoning")
        if not row["completion_tokens"]:
            raise ValueError("Missing positive usage.completion_tokens; throughput cannot be calculated")
        if ended <= first_token:
            raise ValueError("Generation interval is too short to measure throughput")
        row["output_tokens_per_second"] = row["completion_tokens"] / (ended - first_token)
        row["status"] = "ok"
    except (httpx.HTTPError, ValueError, OSError) as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
        if row["latency_ms"] is None:
            row["latency_ms"] = (clock() - started) * 1000
        if first_token is not None and row["ttft_ms"] is None:
            row["ttft_ms"] = (first_token - started) * 1000
    return row


def percentiles(values):
    if not values:
        return {"samples": 0, "p50": None, "p95": None}
    values = sorted(values)
    def percentile(p):
        position = (len(values) - 1) * p
        lower = int(position)
        upper = min(lower + 1, len(values) - 1)
        return round(values[lower] + (values[upper] - values[lower]) * (position - lower), 3)
    return {"samples": len(values), "p50": percentile(0.5), "p95": percentile(0.95)}


def summarize(models, rows):
    summaries = []
    for model in models:
        measured = [r for r in rows if r["model"] == model["id"] and r["phase"] == "measured"]
        successful = [r for r in measured if r["status"] == "ok"]
        warmups = [r for r in rows if r["model"] == model["id"] and r["phase"] == "warmup"]
        summaries.append({"model": model["id"], "measured_requests": len(measured),
                          "successful": len(successful), "errors": len(measured) - len(successful),
                          "warmup_requests": len(warmups),
                          "warmup_errors": sum(r["status"] != "ok" for r in warmups),
                          **{metric: percentiles([r[metric] for r in successful])
                             for metric in ("ttft_ms", "output_tokens_per_second", "latency_ms")}})
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Exact Platform Live model ID; repeat for multiple models")
    parser.add_argument("--runs", type=int, default=10, help="Measured requests per model")
    parser.add_argument("--warmup", type=int, default=1, help="Warm-up requests per model, excluded from statistics")
    parser.add_argument("--concurrency", type=int, default=1, help="Total simultaneous requests")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=int, default=60, help="HTTP phase timeout, seconds")
    parser.add_argument("--prompt-file", type=Path, default=HERE / "benchmark-prompt.txt")
    args = parser.parse_args(argv)
    if min(args.runs, args.concurrency, args.max_tokens, args.timeout) < 1 or args.warmup < 0:
        parser.error("runs, concurrency, max-tokens and timeout must be positive; warmup must be nonnegative")
    load_dotenv(HERE / ".env", override=False)
    load_dotenv(HERE.parents[2] / ".env", override=False)
    key = os.getenv("RESPAN_API_KEY", "").strip()
    if not key:
        parser.error("Set RESPAN_API_KEY in your environment or .env")
    try:
        base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api").rstrip("/")
        if httpx.URL(base_url).path in ("", "/"):
            base_url += "/api"
        prompt = args.prompt_file.read_text().strip()
        if not prompt:
            raise ValueError("Prompt file is empty")
        run_id = "benchmark-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:6]
        with httpx.Client(headers={"Authorization": "Bearer " + key}, timeout=args.timeout,
                          follow_redirects=False) as client:
            catalog = {m["id"]: m for m in discover_models(client, base_url)}
            requested = list(dict.fromkeys(args.model or DEFAULT_MODELS))
            missing = set(requested) - set(catalog)
            if missing:
                raise ValueError(f"Models are not listed under Platform > Models > Live: {sorted(missing)}")
            models = [catalog[name] for name in requested]
            if any(m["model_type"] != "chat" for m in models):
                raise ValueError("The streaming benchmark supports chat models only")
            settings = {"base_url": base_url, "models": models, "runs_per_model": args.runs,
                        "warmup_per_model": args.warmup, "concurrency": args.concurrency,
                        "max_tokens": args.max_tokens, "temperature": 0, "timeout_seconds": args.timeout,
                        "prompt": prompt, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                        "token_count_source": "stream usage.completion_tokens, used verbatim without adding or subtracting reasoning_tokens",
                        "ttft_definition": "request start to first nonempty content or reasoning delta",
                        "tps_formula": "completion_tokens / (latency_seconds - ttft_seconds)"}
            folder = HERE / "results" / run_id
            folder.mkdir(parents=True)
            (folder / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
            print(f"Benchmarking {len(models)} models; {args.runs} measured + {args.warmup} warm-up each.", flush=True)
            print(f"Results: {folder}", flush=True)
            rows = []
            planned = len(models) * (args.runs + args.warmup)
            try:
                with (folder / "requests.jsonl").open("w", buffering=1) as journal:
                    for phase, count in (("warmup", args.warmup), ("measured", args.runs)):
                        pool = ThreadPoolExecutor(max_workers=args.concurrency)
                        try:
                            futures = [pool.submit(measure, client, base_url, model, prompt, args.max_tokens,
                                                   run_id, phase, sample)
                                       for sample in range(1, count + 1) for model in models]
                            for future in as_completed(futures):
                                row = future.result()
                                row = {k: redact(v, key) if isinstance(v, str) else v for k, v in row.items()}
                                rows.append(row)
                                journal.write(json.dumps(row, allow_nan=False) + "\n")
                                print(f"{phase} {row['sample']}: {row['model']} {row['status']}", flush=True)
                        finally:
                            pool.shutdown(wait=True, cancel_futures=True)
            finally:
                with (folder / "requests.csv").open("w", newline="") as file:
                    writer = csv.DictWriter(file, fieldnames=FIELDS)
                    writer.writeheader()
                    for row in rows:
                        writer.writerow({k: "'" + v if isinstance(v, str) and v[:1] in "=+-@" else v
                                         for k, v in row.items()})
                report = {"schema_version": 1, "run_id": run_id, "settings": settings,
                          "complete": len(rows) == planned, "requests_completed": len(rows),
                          "requests_planned": planned, "counts": dict(Counter(r["status"] for r in rows)),
                          "summary": summarize(models, rows)}
                (folder / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
            print(json.dumps(report["summary"], indent=2))
            return 0 if all(r["status"] == "ok" for r in rows) else 1
    except (CatalogError, ValueError, OSError, httpx.HTTPError) as exc:
        print("Error: " + redact(str(exc), key))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
