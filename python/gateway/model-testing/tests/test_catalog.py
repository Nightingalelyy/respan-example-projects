"""Offline contract and credential-boundary checks for catalog discovery."""

import json
import unittest

import httpx

from catalog import CatalogError, discover_models


ROOT = "https://gateway.example/api"


def model(name, **fields):
    return {"model_name": name, "status": "active", "is_verified": True, "model_type": "chat", **fields}


def page(rows, following=None):
    return {"results": rows, "count": len(rows), "next": following}


class CatalogTests(unittest.TestCase):
    def client(self, handler):
        return httpx.Client(transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer secret-key"}, follow_redirects=True)

    def test_paginates_live_platform_rows_without_adding_public_aliases(self):
        paths = []

        def handler(request):
            paths.append(str(request.url))
            self.assertEqual(request.headers["authorization"], "Bearer secret-key")
            self.assertEqual(request.url.path, "/api/models/list/", "Only the platform catalog may be requested")
            self.assertEqual(request.url.params.get("status"), "active")
            if request.url.params.get("page") == "2":
                return httpx.Response(200, json=page(
                    [model("openai/listed-alias"), model("a")],
                    "?status=active&page=3&page_size=1000",
                ))
            if request.url.params.get("page") == "3":
                return httpx.Response(200, json=page([model("org/custom-model")]))
            return httpx.Response(200, json=page(
                [model("a", provider="openai"), model("tts-1")],
                f"{ROOT}/models/list/?status=active&page=2&page_size=1000",
            ))

        with self.client(handler) as client:
            rows = discover_models(client, ROOT)
        self.assertEqual([row["id"] for row in rows], ["a", "openai/listed-alias", "org/custom-model", "tts-1"])
        self.assertNotIn("openai/a", [row["id"] for row in rows])
        self.assertNotIn("openai/tts-1", [row["id"] for row in rows])
        self.assertEqual(rows[0]["provider"], "openai")
        self.assertEqual(len(paths), 3)
        self.assertIn("page_size=1000", paths[0])

    def test_live_means_active_even_when_unverified_or_custom(self):
        entries = [
            model("yes"), model("unverified", is_verified=False),
            model("missing-verification", is_verified=None),
            model("org-custom", affiliation_category="custom", is_verified=False),
            model("deprecated", status="deprecated"), model("archived", status="archived"),
            model("outdated", status="outdated"), model("inactive", status="inactive"),
            model("missing-status", status=None), {"model_name": "absent-status", "model_type": "chat"},
        ]

        def handler(request):
            self.assertEqual(request.url.path, "/api/models/list/")
            return httpx.Response(200, json=page(entries))

        with self.client(handler) as client:
            rows = discover_models(client, ROOT)
        self.assertEqual([row["id"] for row in rows], ["missing-verification", "org-custom", "unverified", "yes"])

    def test_registry_types_only_apply_to_existing_platform_rows(self):
        def handler(request):
            self.assertEqual(request.url.path, "/api/models/list/")
            return httpx.Response(200, json=page([
                model("tts-1"), model("cohere/embed-english-v3.0"),
                model("future", model_type="video"), model("untyped", model_type=None),
            ]))

        with self.client(handler) as client:
            rows = {row["id"]: row for row in discover_models(client, ROOT)}
        self.assertEqual(set(rows), {"tts-1", "cohere/embed-english-v3.0", "future", "untyped"})
        self.assertEqual(rows["tts-1"]["model_type"], "audio")
        self.assertEqual(rows["cohere/embed-english-v3.0"]["model_type"], "embedding")
        self.assertEqual(rows["future"]["model_type"], "unknown")
        self.assertEqual(rows["untyped"]["model_type"], "unknown")

    def test_allowlist_excludes_credentials_and_unused_capabilities(self):
        row = model("safe", provider={"provider_name": "OpenAI", "api_key": "DO-NOT-SAVE"}, extra_kwargs={"token": "DO-NOT-SAVE"}, metadata={"secret": "DO-NOT-SAVE"}, function_call=True, supported_params={"temperature": {"anything": "DO-NOT-SAVE"}})
        def handler(request):
            self.assertEqual(request.url.path, "/api/models/list/")
            return httpx.Response(200, json=page([row]))
        with self.client(handler) as client:
            result = discover_models(client, ROOT)[0]
        self.assertNotIn("DO-NOT-SAVE", json.dumps(result))
        self.assertEqual(result["provider"], "OpenAI")
        self.assertEqual(set(result), {"id", "provider", "model_type", "reasoning_support"})
        self.assertIsNone(result["reasoning_support"])

    def test_rejects_unsafe_pagination_before_sending_credentials(self):
        for following in ["https://evil.example/api/models/list/?page=2", "http://gateway.example/api/models/list/?page=2", "https://gateway.example/other", "https://user:password@gateway.example/api/models/list/", "https://gateway.example/api/models/list/#fragment", "//evil.example/api/models/list/"]:
            with self.subTest(following=following):
                calls = []
                def handler(request):
                    calls.append(request)
                    return httpx.Response(200, json=page([model("a")], following))
                with self.client(handler) as client, self.assertRaises(CatalogError):
                    discover_models(client, ROOT)
                self.assertEqual(len(calls), 1)

    def test_reasoning_flag_accepts_booleans_and_exact_numeric_zero_or_one(self):
        for value, expected in [(True, True), (False, False), (1, True), (0, False), (2, None), ("1", None), (1.0, None)]:
            with self.subTest(value=value):
                def handler(request):
                    self.assertEqual(request.url.path, "/api/models/list/")
                    return httpx.Response(200, json=page([model("a", reasoning_support=value)]))
                with self.client(handler) as client:
                    row = discover_models(client, ROOT)[0]
                self.assertIs(row["reasoning_support"], expected)

    def test_redirect_is_not_followed(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(302, headers={"Location": "https://evil.example/"})
        with self.client(handler) as client, self.assertRaisesRegex(CatalogError, "HTTP 302"):
            discover_models(client, ROOT)
        self.assertEqual(len(calls), 1)

    def test_repeated_page_is_fatal(self):
        def handler(request):
            return httpx.Response(200, json=page([model("a")], str(request.url)))
        with self.client(handler) as client, self.assertRaisesRegex(CatalogError, "repeated"):
            discover_models(client, ROOT)

    def test_partial_failure_never_returns_completed_catalog(self):
        def handler(request):
            if request.url.params.get("page") == "2":
                return httpx.Response(503, text="DO-NOT-SAVE")
            return httpx.Response(200, json=page([model("a")], "?page=2"))
        with self.client(handler) as client, self.assertRaisesRegex(CatalogError, "HTTP 503") as error:
            discover_models(client, ROOT)
        self.assertNotIn("DO-NOT-SAVE", str(error.exception))

    def test_malformed_response_is_fatal(self):
        malformed = [[], {}, {"results": {}}, {"results": [], "count": 9, "next": None}, {"results": [], "count": 0}, {"results": [], "count": 0, "next": 42}, page([None]), page([{"model_name": ""}]), page([{"model_name": 42}])]
        for body in malformed:
            with self.subTest(body=body):
                with self.client(lambda request: httpx.Response(200, json=body)) as client, self.assertRaises(CatalogError):
                    discover_models(client, ROOT)

    def test_invalid_json_and_network_failure_are_sanitized(self):
        def invalid_json(request):
            return httpx.Response(200, text="DO-NOT-SAVE")
        def network_failure(request):
            raise httpx.ConnectError("DO-NOT-SAVE", request=request)
        for handler in (invalid_json, network_failure):
            with self.subTest(handler=handler.__name__):
                with self.client(handler) as client, self.assertRaises(CatalogError) as error:
                    discover_models(client, ROOT)
                self.assertNotIn("DO-NOT-SAVE", str(error.exception))

    def test_invalid_base_url_never_sends_request(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=page([]))
        for url in ["https://[invalid", "https://user:secret@gateway.example/api", "https://gateway.example/api?api_key=secret"]:
            with self.subTest(url=url):
                with self.client(handler) as client, self.assertRaises(CatalogError):
                    discover_models(client, url)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
