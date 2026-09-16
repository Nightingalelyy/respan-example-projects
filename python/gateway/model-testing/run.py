"""Check availability of models listed in platform.respan.ai > Models > Live."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from time import perf_counter
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from catalog import CatalogError, discover_models

HERE = Path(__file__).resolve().parent
FIELDS = ["model", "provider", "model_type", "status", "http_status", "latency_ms", "request_id", "error"]


def redact(text, key):
    if key:
        text = text.replace(key, "[REDACTED]")
    text = re.sub(r"\bsk-[A-Za-z0-9_-]+", "[REDACTED]", text)
    return re.sub(r"(?i)bearer\s+[^\s\"',}]+", "Bearer [REDACTED]", text)


def check_model(client, base_url, model, run_id, max_tokens=64):
    """Availability means a successful inference response, regardless of its answer."""
    row = dict.fromkeys(FIELDS)
    row.update(model=model["id"], provider=model["provider"], model_type=model["model_type"],
               status="unavailable", error="")
    body = {"model": model["id"], "cache_enabled": False, "disable_fallback": True,
            "retry_params": {"retry_enabled": False},
            "metadata": {"availability_run": run_id},
            "custom_identifier": f"{run_id}:{uuid4().hex[:12]}"}
    kind = model["model_type"]
    audio = False
    if kind == "chat":
        endpoint = "/chat/completions"
        token_field = "max_completion_tokens" if model.get("reasoning_support") else "max_tokens"
        body.update(messages=[{"role": "user", "content": "Hi"}], **{token_field: max_tokens})
    elif kind == "embedding":
        endpoint = "/embeddings"
        body.update(input="Hello", encoding_format="float")
    elif kind == "audio" and model["id"].removeprefix("openai/") == "tts-1":
        endpoint = "/audio/speech"
        body.update(input="Hello", voice="alloy", response_format="mp3")
    elif kind == "audio" and model["id"].removeprefix("openai/") in ("whisper-1", "gpt-4o-transcribe"):
        endpoint, audio = "/audio/transcriptions", True
        body["response_format"] = "json"
    else:
        row.update(status="not_tested", error="No availability request defined for this model type")
        return row
    started = perf_counter()
    try:
        if audio:
            with (HERE / "fixtures" / "hello.wav").open("rb") as file:
                data = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in body.items()}
                response = client.post(base_url + endpoint, data=data, files={"file": ("hello.wav", file, "audio/wav")})
        else:
            response = client.post(base_url + endpoint, json=body)
        row.update(http_status=response.status_code,
                   request_id=response.headers.get("x-respan-gateway-request-id"))
        if not response.is_success:
            row["error"] = response.text[:1500]
        elif endpoint == "/audio/speech":
            if response.content and response.headers.get("content-type", "").startswith(("audio/", "application/octet-stream")):
                row["status"] = "available"
            else:
                row["error"] = "Successful HTTP status but no audio response"
        else:
            data = response.json()
            field = "choices" if kind == "chat" else "data" if kind == "embedding" else "text"
            if not isinstance(data, dict) or data.get("error") or field not in data:
                row["error"] = "Unexpected inference response: " + response.text[:1200]
            elif field != "text" and (not isinstance(data[field], list) or not data[field]):
                row["error"] = "Inference response has no results"
            else:
                row["status"] = "available"
    except httpx.TimeoutException:
        row["error"] = "Request timed out"
    except (httpx.HTTPError, ValueError, OSError) as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"
    row["latency_ms"] = round((perf_counter() - started) * 1000)
    return row


def save_results(folder, run_id, planned, rows):
    rows = sorted(rows, key=lambda row: row["model"])
    report = {"run_id": run_id, "models_total": planned, "models_tested": len(rows),
              "complete": len(rows) == planned, "counts": dict(Counter(r["status"] for r in rows)), "results": rows}
    (folder / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    with (folder / "results.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "'" + v if isinstance(v, str) and v[:1] in "=+-@" else v for k, v in row.items()})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Only check this exact model ID; repeat for multiple IDs")
    parser.add_argument("--list", action="store_true", help="List discovered models without inference calls")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--max-tokens", type=int, default=64)
    args = parser.parse_args(argv)
    if min(args.workers, args.timeout, args.max_tokens) < 1:
        parser.error("workers, timeout and max-tokens must be positive")
    load_dotenv(HERE / ".env", override=False)
    load_dotenv(HERE.parents[2] / ".env", override=False)
    key = os.getenv("RESPAN_API_KEY", "").strip()
    if not key:
        parser.error("Set RESPAN_API_KEY in your environment or .env")
    base_url = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api").rstrip("/")
    if httpx.URL(base_url).path in ("", "/"):
        base_url += "/api"
    run_id = "availability-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex[:6]
    folder = HERE / "results" / run_id
    try:
        with httpx.Client(headers={"Authorization": "Bearer " + key}, timeout=args.timeout, follow_redirects=False) as client:
            models = discover_models(client, base_url)
            if args.model:
                missing = set(args.model) - {m["id"] for m in models}
                if missing:
                    raise ValueError(f"Model IDs not found: {sorted(missing)}")
                models = [m for m in models if m["id"] in args.model]
            if not models:
                raise ValueError("No live models discovered")
            if args.list:
                for model in models:
                    print(model["id"])
                print(f"Total: {len(models)}")
                return 0
            folder.mkdir(parents=True)
            (folder / "models.json").write_text(json.dumps(models, indent=2) + "\n")
            print(f"Checking {len(models)} models. Results: {folder}", flush=True)
            rows = []
            pool = ThreadPoolExecutor(max_workers=args.workers)
            try:
                with (folder / "results.jsonl").open("w", buffering=1) as journal:
                    futures = [pool.submit(check_model, client, base_url, m, run_id, args.max_tokens) for m in models]
                    for future in as_completed(futures):
                        row = future.result()
                        row = {k: redact(v, key) if isinstance(v, str) else v for k, v in row.items()}
                        rows.append(row)
                        journal.write(json.dumps(row) + "\n")
                        print(f"[{len(rows)}/{len(models)}] {row['status']}: {row['model']}", flush=True)
            finally:
                pool.shutdown(wait=True, cancel_futures=True)
                report = save_results(folder, run_id, len(models), rows)
            print(json.dumps(report["counts"]))
            return 0 if all(r["status"] == "available" for r in rows) else 1
    except (CatalogError, ValueError, OSError, httpx.HTTPError) as exc:
        print("Error: " + redact(str(exc), key))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
