"""Offline timing, stream-completion, and CLI checks for the benchmark."""

from contextlib import redirect_stdout
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import benchmark


ROOT = "https://gateway.test/api"


def model(name="prism/example", **fields):
    return {"id": name, "provider": "prism", "model_type": "chat", **fields}


def chunk(delta=None, finish=None):
    return {"model": "upstream-model", "choices": [
        {"index": 0, "delta": delta or {}, "finish_reason": finish},
    ]}


def usage(completion=40, reasoning=None):
    value = {"prompt_tokens": 12, "completion_tokens": completion}
    if reasoning is not None:
        value["completion_tokens_details"] = {"reasoning_tokens": reasoning}
    return {"choices": [], "usage": value}


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


class TimedStream(httpx.SyncByteStream):
    """Advance an injected clock at receipt, without sleeping or network I/O."""

    def __init__(self, events, clock, end=2.5):
        self.events, self.clock, self.end = events, clock, end

    def __iter__(self):
        for offset, event in self.events:
            self.clock.now = 100.0 + offset
            if isinstance(event, Exception):
                raise event
            data = event if isinstance(event, str) else json.dumps(event)
            yield f"data: {data}\n\n".encode()
        self.clock.now = 100.0 + self.end


def stream_response(events, clock, end=2.5):
    return httpx.Response(200, stream=TimedStream(events, clock, end), headers={
        "content-type": "text/event-stream; charset=utf-8",
        "x-respan-log-id": "log-1", "x-respan-gateway-request-id": "request-1",
    })


def successful_events():
    return [(0.1, chunk({"role": "assistant"})), (0.2, {"choices": []}),
            (0.5, chunk({"content": "Hello"})), (1.5, chunk({"content": " there"})),
            (2.0, chunk(finish="stop")), (2.4, usage()), (2.5, "[DONE]")]


class BenchmarkTests(unittest.TestCase):
    def measure(self, events, entry=None, end=2.5):
        clock = Clock()
        received = []

        def respond(request):
            received.append(request)
            return stream_response(events, clock, end)

        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            row = benchmark.measure(client, ROOT, entry or model(), "Fixed prompt", 256,
                                    "offline-run", "measured", 1, clock=clock)
        return row, received

    def test_ttft_ignores_control_chunks_and_consumes_usage_after_finish(self):
        row, requests = self.measure(successful_events())
        self.assertEqual(row["status"], "ok")
        self.assertEqual(row["ttft_ms"], 500)
        self.assertEqual(row["latency_ms"], 2500)
        self.assertEqual(row["completion_tokens"], 40)
        self.assertEqual(row["output_tokens_per_second"], 20)
        self.assertEqual(row["prompt_tokens"], 12)
        self.assertEqual(row["finish_reason"], "stop")
        self.assertEqual(row["log_id"], "log-1")
        self.assertEqual(row["request_id"], "request-1")
        self.assertEqual(row["response_model"], "upstream-model")
        self.assertEqual(len(requests), 1)
        self.assertEqual(str(requests[0].url), ROOT + "/chat/completions")
        payload = json.loads(requests[0].content)
        self.assertEqual(payload["messages"], [{"role": "user", "content": "Fixed prompt"}])
        self.assertEqual(payload["model"], "prism/example")
        self.assertEqual(payload["max_tokens"], 256)
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["stream_options"], {"include_usage": True})
        self.assertTrue(payload["stream"])
        self.assertFalse(payload["cache_enabled"])
        self.assertTrue(payload["disable_fallback"])
        self.assertFalse(payload["retry_params"]["retry_enabled"])
        self.assertEqual(payload["custom_identifier"], row["custom_identifier"])

    def test_reasoning_starts_ttft_and_tokens_are_not_double_counted(self):
        for field in ("reasoning_content", "reasoning"):
            events = [(0.1, chunk({"role": "assistant"})),
                      (0.5, chunk({field: "Think first"})),
                      (1.5, chunk({"content": "Answer"})),
                      (2.0, chunk(finish="length")), (2.4, usage(40, 30)), (2.5, "[DONE]")]
            with self.subTest(field=field):
                row, requests = self.measure(events, model(reasoning_support=True))
                self.assertEqual(row["status"], "ok")
                self.assertEqual(row["ttft_ms"], 500)
                self.assertEqual(row["reasoning_tokens"], 30)
                self.assertEqual(row["completion_tokens"], 40)
                self.assertEqual(row["output_tokens_per_second"], 20)
                payload = json.loads(requests[0].content)
                self.assertEqual(payload["max_completion_tokens"], 256)
                self.assertNotIn("max_tokens", payload)

    def test_done_and_clean_eof_after_finish_are_valid(self):
        for done in (True, False):
            events = successful_events()
            if not done:
                events.pop()
            with self.subTest(done=done):
                row, _ = self.measure(events)
                self.assertEqual(row["status"], "ok")
                self.assertEqual(row["stream_end"], "done" if done else "eof")
                self.assertEqual(row["output_tokens_per_second"], 20)

    def test_incomplete_stream_or_missing_usage_cannot_produce_throughput(self):
        cases = [
            ([(0.5, chunk({"content": "partial"})), (2.4, usage())], "finish_reason"),
            ([(0.5, chunk({"content": "partial"})), (2.4, usage()), (2.5, "[DONE]")], "finish_reason"),
            ([(0.5, chunk({"content": "answer"})), (2.0, chunk(finish="stop"))], "completion_tokens"),
            ([(0.5, chunk({"role": "assistant"})), (2.0, chunk(finish="stop")), (2.4, usage())], "no generated"),
        ]
        for events, error in cases:
            with self.subTest(error=error, events=events):
                row, _ = self.measure(events)
                self.assertEqual(row["status"], "error")
                self.assertIsNone(row["output_tokens_per_second"])
                self.assertIn(error, row["error"])

    def test_in_stream_error_after_finish_is_failure_even_with_http_200(self):
        events = successful_events()[:-1] + [(2.5, {"error": {"message": "upstream failed"}})]
        row, requests = self.measure(events)
        self.assertEqual(len(requests), 1)
        self.assertEqual(row["http_status"], 200)
        self.assertEqual(row["status"], "error")
        self.assertIn("upstream failed", row["error"])
        self.assertEqual(row["ttft_ms"], 500)
        self.assertIsNone(row["output_tokens_per_second"])

    def test_invalid_usage_and_nonpositive_generation_interval_are_errors(self):
        for invalid in (None, 0, -1, True, "40"):
            events = successful_events()
            events[-2] = (2.4, usage(invalid))
            with self.subTest(completion_tokens=invalid):
                row, _ = self.measure(events)
                self.assertEqual(row["status"], "error")
                self.assertIsNone(row["output_tokens_per_second"])
        events = [(0.5, chunk({"content": "answer"})), (0.5, chunk(finish="stop")), (0.5, usage())]
        row, _ = self.measure(events, end=0.5)
        self.assertEqual(row["status"], "error")
        self.assertIn("too short", row["error"])
        self.assertIsNone(row["output_tokens_per_second"])

    def test_http_errors_and_interrupted_stream_are_recorded_without_retry(self):
        for status in (401, 429, 503):
            calls = []

            def respond(request):
                calls.append(request)
                return httpx.Response(status, text="Unavailable")

            with self.subTest(status=status), httpx.Client(transport=httpx.MockTransport(respond)) as client:
                row = benchmark.measure(client, ROOT, model(), "prompt", 256, "run", "measured", 1,
                                        clock=iter([100, 102]).__next__)
            self.assertEqual(len(calls), 1)
            self.assertEqual(row["status"], "error")
            self.assertEqual(row["http_status"], status)
            self.assertIn(f"HTTP {status}", row["error"])
            self.assertEqual(row["latency_ms"], 2000)
        row, requests = self.measure([(0.5, chunk({"content": "partial"})),
                                      (2.0, httpx.ReadTimeout("stalled"))])
        self.assertEqual(len(requests), 1)
        self.assertEqual(row["status"], "error")
        self.assertIn("ReadTimeout", row["error"])
        self.assertEqual(row["ttft_ms"], 500)
        self.assertIsNone(row["output_tokens_per_second"])

    def test_percentiles_and_summary_exclude_warmups_and_failed_measurements(self):
        rows = [dict(model="a", phase=phase, status=status, ttft_ms=value,
                     latency_ms=value, output_tokens_per_second=value)
                for phase, status, value in [
                    ("warmup", "ok", 9999), ("warmup", "error", None),
                    ("measured", "ok", 10), ("measured", "ok", 30), ("measured", "error", None),
                ]]
        report = benchmark.summarize([model("a"), model("b")], rows)
        self.assertEqual(report[0]["measured_requests"], 3)
        self.assertEqual(report[0]["successful"], 2)
        self.assertEqual(report[0]["errors"], 1)
        self.assertEqual(report[0]["warmup_requests"], 2)
        self.assertEqual(report[0]["warmup_errors"], 1)
        for metric in ("ttft_ms", "latency_ms", "output_tokens_per_second"):
            self.assertEqual(report[0][metric], {"samples": 2, "p50": 20, "p95": 29})
            self.assertEqual(report[1][metric], {"samples": 0, "p50": None, "p95": None})
        self.assertEqual(benchmark.percentiles([7]), {"samples": 1, "p50": 7, "p95": 7})

    def invoke(self, here, handler, args):
        client = httpx.Client(transport=httpx.MockTransport(handler),
                              headers={"Authorization": "Bearer offline-secret"})
        self.addCleanup(client.close)
        prompt = here / "fixed-prompt.txt"
        prompt.write_text("Fixed benchmark workload\n")
        with patch.dict(os.environ, {"RESPAN_API_KEY": "offline-secret", "RESPAN_BASE_URL": ROOT}, clear=True), \
                patch.object(benchmark, "HERE", here), patch.object(benchmark, "load_dotenv"), \
                patch.object(benchmark.httpx, "Client", return_value=client), redirect_stdout(io.StringIO()):
            return benchmark.main(["--prompt-file", str(prompt), *args])

    def test_cli_checks_live_catalog_warms_up_then_exports_reproducible_results(self):
        received = []

        def respond(request):
            self.assertEqual(request.headers["authorization"], "Bearer offline-secret")
            if request.method == "GET":
                self.assertEqual(request.url.path, "/api/models/list/")
                self.assertEqual(request.url.params.get("status"), "active")
                entries = [{"model_name": name, "status": "active", "model_type": "chat"}
                           for name in ("prism/one", "prism/two")]
                return httpx.Response(200, json={"results": entries, "count": 2, "next": None})
            payload = json.loads(request.content)
            received.append(payload)
            return stream_response(successful_events(), Clock())

        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder) / "python" / "gateway" / "model-testing"
            here.mkdir(parents=True)
            status = self.invoke(here, respond, ["--model", "prism/one", "--model", "prism/two",
                                                "--runs", "2", "--warmup", "1", "--concurrency", "1"])
            self.assertEqual(status, 0)
            self.assertEqual([p["metadata"]["benchmark_phase"] for p in received],
                             ["warmup", "warmup", "measured", "measured", "measured", "measured"])
            output = next((here / "results").iterdir())
            settings = json.loads((output / "settings.json").read_text())
            self.assertEqual(settings["prompt"], "Fixed benchmark workload")
            self.assertEqual(settings["prompt_sha256"], hashlib.sha256(b"Fixed benchmark workload").hexdigest())
            self.assertEqual(settings["runs_per_model"], 2)
            self.assertEqual(settings["warmup_per_model"], 1)
            self.assertEqual(settings["concurrency"], 1)
            self.assertEqual(settings["max_tokens"], 256)
            report = json.loads((output / "summary.json").read_text())
            self.assertTrue(report["complete"])
            self.assertEqual(report["requests_completed"], 6)
            self.assertEqual(report["requests_planned"], 6)
            self.assertEqual(report["counts"], {"ok": 6})
            self.assertEqual(report["settings"], settings)
            for item in report["summary"]:
                self.assertEqual(item["successful"], 2)
                self.assertEqual(item["ttft_ms"]["samples"], 2)
            rows = [json.loads(line) for line in (output / "requests.jsonl").read_text().splitlines()]
            with (output / "requests.csv").open(newline="") as file:
                exported = list(csv.DictReader(file))
            self.assertEqual(len(exported), 6)
            self.assertEqual([r["custom_identifier"] for r in rows], [r["custom_identifier"] for r in exported])
            self.assertEqual(len({r["custom_identifier"] for r in rows}), 6)

    def test_cli_rejects_unlisted_alias_retired_and_nonchat_models_before_calls(self):
        for requested in ("example", "prism/retired", "prism/embedding"):
            calls = []

            def respond(request):
                calls.append(request)
                self.assertEqual(request.method, "GET")
                self.assertEqual(request.url.path, "/api/models/list/")
                entries = [
                    {"model_name": "prism/example", "status": "active", "model_type": "chat"},
                    {"model_name": "prism/retired", "status": "archived", "model_type": "chat"},
                    {"model_name": "prism/embedding", "status": "active", "model_type": "embedding"},
                ]
                return httpx.Response(200, json={"results": entries, "count": 3, "next": None})

            with self.subTest(requested=requested), tempfile.TemporaryDirectory() as folder:
                here = Path(folder) / "python" / "gateway" / "model-testing"
                here.mkdir(parents=True)
                self.assertEqual(self.invoke(here, respond, ["--model", requested, "--runs", "1"]), 2)
                self.assertEqual(len(calls), 1)
                self.assertFalse((here / "results").exists())

    def test_cli_retains_and_redacts_failed_attempts_without_summarizing_them(self):
        def respond(request):
            if request.method == "GET":
                return httpx.Response(200, json={"count": 1, "next": None, "results": [
                    {"model_name": "=formula", "status": "active", "model_type": "chat"},
                ]})
            return httpx.Response(503, text="offline-secret Bearer provider-secret sk-provider-key")

        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder) / "python" / "gateway" / "model-testing"
            here.mkdir(parents=True)
            self.assertEqual(self.invoke(here, respond, ["--model", "=formula", "--runs", "1", "--warmup", "1"]), 1)
            output = next((here / "results").iterdir())
            report = json.loads((output / "summary.json").read_text())
            self.assertTrue(report["complete"])
            self.assertEqual(report["counts"], {"error": 2})
            self.assertEqual(report["summary"][0]["warmup_errors"], 1)
            self.assertEqual(report["summary"][0]["errors"], 1)
            self.assertEqual(report["summary"][0]["ttft_ms"]["samples"], 0)
            with (output / "requests.csv").open(newline="") as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["model"], "'=formula")
            for name in ("settings.json", "requests.jsonl", "requests.csv", "summary.json"):
                content = (output / name).read_text()
                for secret in ("offline-secret", "provider-secret", "sk-provider-key"):
                    self.assertNotIn(secret, content)


if __name__ == "__main__":
    unittest.main()
