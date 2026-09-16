"""Small offline checks for model availability; all HTTP uses MockTransport."""

from contextlib import redirect_stdout
import csv
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

import run


def model(name="example-model", kind="chat", **metadata):
    return {"id": name, "provider": "example", "model_type": kind, **metadata}


class AvailabilityTests(unittest.TestCase):
    def check(self, response, entry=None):
        with httpx.Client(transport=httpx.MockTransport(lambda request: response)) as client:
            return run.check_model(client, "https://gateway.test/api", entry or model(), "offline-run")

    def test_success_is_available_regardless_of_answer_or_finish_reason(self):
        for content, finish_reason in (("Any arbitrary answer.", "stop"), ("", "length"), (None, "length")):
            with self.subTest(content=content, finish_reason=finish_reason):
                row = self.check(httpx.Response(200, json={"choices": [{
                    "message": {"role": "assistant", "content": content}, "finish_reason": finish_reason,
                }]}))
                self.assertEqual(row["status"], "available")
                self.assertEqual(row["http_status"], 200)
                self.assertEqual(row["error"], "")
                self.assertGreaterEqual(row["latency_ms"], 0)

    def test_chat_request_preserves_model_and_uses_reasoning_token_field(self):
        received = []

        def respond(request):
            received.append(request)
            return httpx.Response(200, json={"choices": [{}]},
                                  headers={"x-respan-gateway-request-id": "gateway-request-1"})

        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            row = run.check_model(client, "https://gateway.test/api", model(reasoning_support=True), "offline", 128)
        self.assertEqual(len(received), 1)
        self.assertEqual(str(received[0].url), "https://gateway.test/api/chat/completions")
        payload = json.loads(received[0].content)
        self.assertEqual(payload["model"], "example-model")
        self.assertEqual(payload["messages"], [{"role": "user", "content": "Hi"}])
        self.assertEqual(payload["max_completion_tokens"], 128)
        self.assertNotIn("max_tokens", payload)
        self.assertFalse(payload["cache_enabled"])
        self.assertTrue(payload["disable_fallback"])
        self.assertFalse(payload["retry_params"]["retry_enabled"])
        self.assertEqual(row["request_id"], "gateway-request-1")

    def test_http_errors_and_missing_inference_results_are_unavailable(self):
        responses = [httpx.Response(status, text="model unavailable") for status in (401, 403, 404, 429, 500)]
        responses += [httpx.Response(200, json=value) for value in (
            {"error": {"message": "upstream failure"}, "choices": [{}]},
            {}, [], {"choices": []}, {"choices": None}, {"choices": "not results"},
        )]
        responses.append(httpx.Response(200, text="invalid JSON"))
        for response in responses:
            with self.subTest(status=response.status_code, body=response.text):
                row = self.check(response)
                self.assertEqual(row["status"], "unavailable")
                self.assertEqual(row["http_status"], response.status_code)
                self.assertTrue(row["error"])

    def test_timeout_and_connection_failure_are_recorded_without_retry(self):
        for error in (httpx.ReadTimeout, httpx.ConnectError):
            requests = []

            def fail(request):
                requests.append(request)
                raise error("offline failure", request=request)

            with self.subTest(error=error), httpx.Client(transport=httpx.MockTransport(fail)) as client:
                row = run.check_model(client, "https://gateway.test/api", model(), "offline")
            self.assertEqual(row["status"], "unavailable")
            self.assertIsNone(row["http_status"])
            self.assertTrue(row["error"])
            self.assertEqual(len(requests), 1)

    def test_embeddings_and_binary_speech_use_their_routes(self):
        for entry, endpoint, response in (
            (model("embedding-model", "embedding"), "/embeddings", httpx.Response(200, json={"data": [{"embedding": [0.1]}]})),
            (model("openai/tts-1", "audio"), "/audio/speech", httpx.Response(200, content=b"audio", headers={"content-type": "audio/mpeg"})),
        ):
            received = []

            def respond(request):
                received.append(request)
                return response

            with self.subTest(entry=entry), httpx.Client(transport=httpx.MockTransport(respond)) as client:
                row = run.check_model(client, "https://gateway.test/api", entry, "offline")
            self.assertEqual(row["status"], "available")
            self.assertEqual(received[0].url.path, "/api" + endpoint)
            self.assertNotIn("max_tokens", json.loads(received[0].content))
        for response in (httpx.Response(200, content=b"", headers={"content-type": "audio/mpeg"}),
                         httpx.Response(200, json={"error": "failed"})):
            self.assertEqual(self.check(response, model("tts-1", "audio"))["status"], "unavailable")
        self.assertEqual(self.check(httpx.Response(200, json={"data": []}), model("embedding-model", "embedding"))["status"], "unavailable")

    def test_transcription_uploads_fixture_and_accepts_arbitrary_transcript(self):
        received = []

        def respond(request):
            received.append(request)
            return httpx.Response(200, json={"text": "Any transcript is sufficient."})

        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            row = run.check_model(client, "https://gateway.test/api", model("whisper-1", "audio"), "offline")
        self.assertEqual(row["status"], "available")
        self.assertEqual(received[0].url.path, "/api/audio/transcriptions")
        self.assertIn("multipart/form-data", received[0].headers["content-type"])
        self.assertIn(b'filename="hello.wav"', received[0].content)
        self.assertIn(b"RIFF", received[0].content)

    def test_run_only_calls_and_exports_models_listed_live_on_platform(self):
        called_models = []

        def respond(request):
            if request.method == "GET":
                self.assertEqual(request.url.path, "/api/models/list/", "Public-only aliases must never enter discovery")
                self.assertEqual(request.url.params.get("status"), "active")
                entries = [
                    {"model_name": "listed", "status": "active", "is_verified": True, "model_type": "chat"},
                    {"model_name": "listed-unverified", "status": "active", "is_verified": False, "model_type": "chat"},
                    {"model_name": "retired", "status": "archived", "is_verified": True, "model_type": "chat"},
                ]
                return httpx.Response(200, json={"results": entries, "count": len(entries), "next": None})
            self.assertEqual(request.url.path, "/api/chat/completions")
            called_models.append(json.loads(request.content)["model"])
            return httpx.Response(200, json={"choices": [{}]})

        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder) / "python" / "gateway" / "model-testing"
            here.mkdir(parents=True)
            client = httpx.Client(transport=httpx.MockTransport(respond))
            self.addCleanup(client.close)
            with patch.dict(os.environ, {"RESPAN_API_KEY": "offline-key"}, clear=True), \
                    patch.object(run, "HERE", here), patch.object(run, "load_dotenv"), \
                    patch.object(run.httpx, "Client", return_value=client), redirect_stdout(io.StringIO()):
                status = run.main(["--workers", "1"])
            self.assertEqual(status, 0)
            self.assertEqual(called_models, ["listed", "listed-unverified"])
            output = next((here / "results").iterdir())
            manifest = json.loads((output / "models.json").read_text())
            report = json.loads((output / "results.json").read_text())
            self.assertEqual([entry["id"] for entry in manifest], called_models)
            self.assertEqual([row["model"] for row in report["results"]], called_models)
            self.assertEqual(report["models_total"], 2)
            self.assertEqual(report["counts"], {"available": 2})

    def test_results_export_counts_and_redacts_secrets(self):
        key = "offline-respan-secret"

        def respond(request):
            if json.loads(request.content)["model"] == "=formula":
                return httpx.Response(200, json={"choices": [{}]})
            return httpx.Response(403, text=f"{key} Bearer provider-secret sk-provider-key")

        with tempfile.TemporaryDirectory() as folder:
            here = Path(folder) / "python" / "gateway" / "model-testing"
            here.mkdir(parents=True)
            client = httpx.Client(transport=httpx.MockTransport(respond))
            self.addCleanup(client.close)
            with patch.dict(os.environ, {"RESPAN_API_KEY": key}, clear=True), \
                    patch.object(run, "HERE", here), patch.object(run, "load_dotenv"), \
                    patch.object(run.httpx, "Client", return_value=client), \
                    patch.object(run, "discover_models", return_value=[model("z-error"), model("=formula")]), \
                    redirect_stdout(io.StringIO()):
                status = run.main(["--workers", "1"])
            self.assertEqual(status, 1)
            output = next((here / "results").iterdir())
            report = json.loads((output / "results.json").read_text())
            self.assertTrue(report["complete"])
            self.assertEqual(report["models_tested"], 2)
            self.assertEqual(report["counts"], {"available": 1, "unavailable": 1})
            self.assertEqual(report["results"][0]["model"], "=formula")
            self.assertEqual(len((output / "results.jsonl").read_text().splitlines()), 2)
            with (output / "results.csv").open(newline="") as stream:
                csv_rows = list(csv.DictReader(stream))
            self.assertEqual(csv_rows[0]["model"], "'=formula")
            for name in ("results.json", "results.csv", "results.jsonl"):
                content = (output / name).read_text()
                for secret in (key, "provider-secret", "sk-provider-key"):
                    self.assertNotIn(secret, content)


if __name__ == "__main__":
    unittest.main()
