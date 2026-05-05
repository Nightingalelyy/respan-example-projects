#!/usr/bin/env python3
"""Haystack complex edge cases with Respan tracing.

This example exercises Haystack indexing, retrieval, routing, prompt building,
joining, answer building, custom components, provider-shaped generator spans,
and chat-message outputs. It uses deterministic local generators so the trace
is stable while still covering multiple model-provider output shapes.

Run:
    python complex_edge_cases.py
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import replace
from typing import Any

from dotenv import find_dotenv, load_dotenv


load_dotenv(find_dotenv(usecwd=True), override=True)

RESPAN_API_KEY = os.environ["RESPAN_API_KEY"]
RESPAN_BASE_URL = os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api")
RUN_ID = os.getenv("RESPAN_HAYSTACK_RUN_ID", f"haystack-{uuid.uuid4().hex[:12]}")

os.environ.setdefault("HAYSTACK_CONTENT_TRACING_ENABLED", "true")
os.environ.setdefault("HAYSTACK_AUTO_TRACE_ENABLED", "true")

from respan import Respan, workflow  # noqa: E402
from respan_instrumentation_haystack import HaystackInstrumentor  # noqa: E402


respan = Respan(
    app_name="haystack-complex-edge-cases",
    api_key=RESPAN_API_KEY,
    base_url=RESPAN_BASE_URL,
    instrumentations=[HaystackInstrumentor()],
    metadata={
        "example": "haystack-complex-edge-cases",
        "run_id": RUN_ID,
    },
)

from haystack import Document, Pipeline, component  # noqa: E402
from haystack.components.builders import (  # noqa: E402
    AnswerBuilder,
    ChatPromptBuilder,
    PromptBuilder,
)
from haystack.components.converters import OutputAdapter  # noqa: E402
from haystack.components.joiners import DocumentJoiner  # noqa: E402
from haystack.components.preprocessors import DocumentCleaner, DocumentSplitter  # noqa: E402
from haystack.components.retrievers.in_memory import (  # noqa: E402
    InMemoryBM25Retriever,
    InMemoryEmbeddingRetriever,
)
from haystack.components.routers import ConditionalRouter  # noqa: E402
from haystack.dataclasses import ChatMessage  # noqa: E402
from haystack.components.writers import DocumentWriter  # noqa: E402
from haystack.document_stores.in_memory import InMemoryDocumentStore  # noqa: E402
from haystack.document_stores.types import DuplicatePolicy  # noqa: E402


def print_result(label: str, value: Any) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


def deterministic_embedding(text: str) -> list[float]:
    lowered = text.lower()
    checkout = 1.0 if "checkout" in lowered or "inventory" in lowered else 0.1
    billing = 1.0 if "billing" in lowered or "payment" in lowered else 0.1
    routing = 1.0 if "region" in lowered or "traffic" in lowered else 0.1
    return [checkout, billing, routing]


PROVIDER_COMPLETION_CASES: dict[str, dict[str, Any]] = {
    "openai": {
        "provider": "openai",
        "model": "gpt-4.1-nano",
        "usage": {"prompt_tokens": 31, "completion_tokens": 11},
    },
    "azure": {
        "provider": "azure",
        "model": "azure/gpt-4o-mini",
        "usage": {"input_tokens": 29, "output_tokens": 10},
    },
    "anthropic": {
        "provider": "anthropic",
        "model": "anthropic/claude-3-5-haiku",
        "usage": {"input_tokens": 33, "output_tokens": 12},
    },
    "huggingface": {
        "provider": "huggingface",
        "model": "huggingface/mistral-small",
        "usage": {"input_tokens": 27, "generated_tokens": 9},
    },
    "gemini": {
        "provider": "google",
        "model": "google/gemini-1.5-flash",
        "usage": {
            "prompt_token_count": 30,
            "candidates_token_count": 8,
            "total_token_count": 38,
        },
    },
}

PROVIDER_CHAT_CASES: dict[str, dict[str, Any]] = {
    "openai_chat": {
        "provider": "openai",
        "model": "gpt-4.1-nano",
        "usage": {"prompt_tokens": 24, "completion_tokens": 8},
    },
    "azure_chat": {
        "provider": "azure",
        "model": "azure/gpt-4o-mini",
        "usage": {"input_tokens": 25, "output_tokens": 8},
    },
    "anthropic_chat": {
        "provider": "anthropic",
        "model": "anthropic/claude-3-5-haiku",
        "usage": {"input_tokens": 26, "output_tokens": 9},
    },
    "huggingface_chat": {
        "provider": "huggingface",
        "model": "huggingface/zephyr",
        "usage": {"input_tokens": 22, "generated_tokens": 7},
    },
}


@component
class StaticIncidentDocumentSource:
    """Produces documents with nested metadata, escaped Unicode, and long content."""

    @component.output_types(documents=list[Document])
    def run(self) -> dict[str, list[Document]]:
        docs = [
            Document(
                content=(
                    "Checkout latency is usually caused by inventory lock "
                    "contention. Page the incident commander when p95 exceeds "
                    "two seconds for more than five minutes."
                ),
                meta={
                    "service": "checkout",
                    "severity": "high",
                    "source": "runbook.checkout",
                    "labels": ["latency", "locks", "customer-impact"],
                },
            ),
            Document(
                content=(
                    "Billing retries are acceptable below two percent. Above "
                    "that threshold, reconcile provider errors and queue lag."
                ),
                meta={
                    "service": "billing",
                    "severity": "medium",
                    "source": "runbook.billing",
                    "labels": ["payments", "retry"],
                },
            ),
            Document(
                content=(
                    "If a region is unhealthy, shift traffic to the warm standby "
                    "and verify cache freshness before restoring traffic."
                ),
                meta={
                    "service": "traffic",
                    "severity": "high",
                    "source": "runbook.traffic",
                    "labels": ["routing", "failover"],
                    "escaped_note": "\\u4f60\\u597d / \\u3053\\u3093\\u306b\\u3061\\u306f",
                },
            ),
        ]
        return {"documents": docs}


@component
class DeterministicDocumentEmbedder:
    """Adds small deterministic embeddings so embedding retrieval is offline."""

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document]) -> dict[str, list[Document]]:
        embedded_docs = []
        for document in documents:
            embedded_docs.append(
                replace(
                    document,
                    embedding=deterministic_embedding(document.content or ""),
                )
            )
        return {"documents": embedded_docs}


@component
class QueryEmbedder:
    @component.output_types(query_embedding=list[float])
    def run(self, query: str) -> dict[str, list[float]]:
        return {"query_embedding": deterministic_embedding(query)}


@component
class IncidentPayloadAssembler:
    @component.output_types(payload=dict[str, Any])
    def run(
        self,
        query: str,
        bm25_documents: list[Document],
        embedding_documents: list[Document],
        route: str,
    ) -> dict[str, dict[str, Any]]:
        return {
            "payload": {
                "query": query,
                "route": route,
                "bm25_sources": [doc.meta.get("source") for doc in bm25_documents],
                "embedding_sources": [
                    doc.meta.get("source") for doc in embedding_documents
                ],
            }
        }


@component
class ProviderCompletionGenerator:
    """Completion-shaped generator with provider-specific model and usage metadata."""

    def __init__(self, provider_config: dict[str, Any], reply: str | None = None) -> None:
        self.provider_config = provider_config
        self.reply = reply

    @component.output_types(replies=list[str], meta=list[dict[str, Any]])
    def run(self, prompt: str) -> dict[str, Any]:
        reply = self.reply or (
            f"{self.provider_config['provider']} recommends escalation with "
            "traffic failover checks."
        )
        return {
            "replies": [reply],
            "meta": [
                {
                    "provider": self.provider_config["provider"],
                    "model": self.provider_config["model"],
                    "usage": self.provider_config["usage"],
                    "finish_reason": "stop",
                    "prompt_chars": len(prompt),
                }
            ],
        }


@component
class ProviderChatGenerator:
    """Chat-shaped generator that returns Haystack ChatMessage replies."""

    def __init__(self, provider_config: dict[str, Any]) -> None:
        self.provider_config = provider_config

    @component.output_types(replies=list[ChatMessage], meta=list[dict[str, Any]])
    def run(self, messages: list[ChatMessage]) -> dict[str, Any]:
        user_text = messages[-1].text if messages else ""
        reply = (
            f"{self.provider_config['provider']} chat response for "
            f"{user_text[:48].strip()}"
        )
        return {
            "replies": [ChatMessage.from_assistant(reply)],
            "meta": [
                {
                    "provider": self.provider_config["provider"],
                    "model": self.provider_config["model"],
                    "usage": self.provider_config["usage"],
                    "finish_reason": "stop",
                }
            ],
        }


def build_indexing_pipeline(
    document_store: InMemoryDocumentStore,
) -> Pipeline:
    pipeline = Pipeline()
    pipeline.add_component("document_source", StaticIncidentDocumentSource())
    pipeline.add_component(
        "document_cleaner",
        DocumentCleaner(
            remove_extra_whitespaces=True,
            unicode_normalization="NFKC",
            strip_whitespaces=True,
        ),
    )
    pipeline.add_component(
        "document_splitter",
        DocumentSplitter(split_by="word", split_length=24, split_overlap=4),
    )
    pipeline.add_component("document_embedder", DeterministicDocumentEmbedder())
    pipeline.add_component(
        "document_writer",
        DocumentWriter(document_store, policy=DuplicatePolicy.OVERWRITE),
    )
    pipeline.connect("document_source.documents", "document_cleaner.documents")
    pipeline.connect("document_cleaner.documents", "document_splitter.documents")
    pipeline.connect("document_splitter.documents", "document_embedder.documents")
    pipeline.connect("document_embedder.documents", "document_writer.documents")
    return pipeline


def build_rag_pipeline(document_store: InMemoryDocumentStore) -> Pipeline:
    prompt_template = """You are a deterministic incident assistant.
Route: {{ route }}
BM25 sources: {{ payload.bm25_sources | join(", ") }}
Embedding sources: {{ payload.embedding_sources | join(", ") }}
Documents:
{% for document in documents -%}
- {{ document.meta.source }} | {{ document.meta.severity }} | {{ document.content }}
{% endfor -%}
Question: {{ query }}
Answer:"""

    pipeline = Pipeline()
    pipeline.add_component(
        "bm25_retriever",
        InMemoryBM25Retriever(document_store=document_store, top_k=3),
    )
    pipeline.add_component("query_embedder", QueryEmbedder())
    pipeline.add_component(
        "embedding_retriever",
        InMemoryEmbeddingRetriever(document_store=document_store, top_k=3),
    )
    pipeline.add_component(
        "document_joiner",
        DocumentJoiner(join_mode="merge", top_k=4, sort_by_score=True),
    )
    pipeline.add_component(
        "severity_router",
        ConditionalRouter(
            routes=[
                {
                    "condition": '{{ severity in ["high", "critical"] }}',
                    "output": "{{ service }}:page-commander",
                    "output_name": "route",
                    "output_type": str,
                },
                {
                    "condition": '{{ severity not in ["high", "critical"] }}',
                    "output": "{{ service }}:watch-channel",
                    "output_name": "route",
                    "output_type": str,
                },
            ]
        ),
    )
    pipeline.add_component(
        "route_adapter",
        OutputAdapter(
            template="{{ route }} | normalized={{ route | lower }}",
            output_type=str,
        ),
    )
    pipeline.add_component("payload_assembler", IncidentPayloadAssembler())
    pipeline.add_component(
        "prompt_builder",
        PromptBuilder(
            template=prompt_template,
            required_variables=["documents", "payload", "query", "route"],
        ),
    )
    pipeline.add_component(
        "llm",
        ProviderCompletionGenerator(
            PROVIDER_COMPLETION_CASES["openai"],
            reply=(
                "Escalate checkout latency, inspect inventory locks, and keep "
                "traffic failover ready until p95 recovers."
            ),
        ),
    )
    pipeline.add_component("answer_builder", AnswerBuilder())

    pipeline.connect("query_embedder.query_embedding", "embedding_retriever.query_embedding")
    pipeline.connect("bm25_retriever.documents", "document_joiner.documents")
    pipeline.connect("embedding_retriever.documents", "document_joiner.documents")
    pipeline.connect("severity_router.route", "route_adapter.route")
    pipeline.connect("bm25_retriever.documents", "payload_assembler.bm25_documents")
    pipeline.connect(
        "embedding_retriever.documents", "payload_assembler.embedding_documents"
    )
    pipeline.connect("route_adapter.output", "payload_assembler.route")
    pipeline.connect("document_joiner.documents", "prompt_builder.documents")
    pipeline.connect("payload_assembler.payload", "prompt_builder.payload")
    pipeline.connect("route_adapter.output", "prompt_builder.route")
    pipeline.connect("prompt_builder.prompt", "llm.prompt")
    pipeline.connect("document_joiner.documents", "answer_builder.documents")
    pipeline.connect("llm.replies", "answer_builder.replies")
    pipeline.connect("llm.meta", "answer_builder.meta")
    return pipeline


def build_router_only_pipeline() -> Pipeline:
    pipeline = Pipeline()
    pipeline.add_component(
        "severity_router",
        ConditionalRouter(
            routes=[
                {
                    "condition": '{{ severity in ["high", "critical"] }}',
                    "output": "{{ incident_id }}:escalate",
                    "output_name": "escalation_path",
                    "output_type": str,
                },
                {
                    "condition": '{{ severity not in ["high", "critical"] }}',
                    "output": "{{ incident_id }}:monitor",
                    "output_name": "monitoring_path",
                    "output_type": str,
                },
            ]
        ),
    )
    pipeline.add_component(
        "route_uppercase_adapter",
        OutputAdapter(template="{{ escalation_path | upper }}", output_type=str),
    )
    pipeline.connect(
        "severity_router.escalation_path", "route_uppercase_adapter.escalation_path"
    )
    return pipeline


def build_provider_matrix_pipeline() -> Pipeline:
    completion_template = (
        "Provider matrix check. Route={{ route }}. Question={{ question }}. "
        "Return one short action."
    )
    chat_template = [
        ChatMessage.from_system("You are validating Haystack chat provider spans."),
        ChatMessage.from_user(
            "Route={{ route }}\nQuestion={{ question }}\nReturn one short action."
        ),
    ]

    pipeline = Pipeline()
    pipeline.add_component(
        "completion_prompt_builder",
        PromptBuilder(
            template=completion_template,
            required_variables=["question", "route"],
        ),
    )
    pipeline.add_component(
        "chat_prompt_builder",
        ChatPromptBuilder(
            template=chat_template,
            required_variables=["question", "route"],
        ),
    )

    for provider_name, provider_config in PROVIDER_COMPLETION_CASES.items():
        component_name = f"{provider_name}_completion_llm"
        pipeline.add_component(
            component_name,
            ProviderCompletionGenerator(provider_config),
        )
        pipeline.connect("completion_prompt_builder.prompt", f"{component_name}.prompt")

    for provider_name, provider_config in PROVIDER_CHAT_CASES.items():
        component_name = f"{provider_name}_llm"
        pipeline.add_component(component_name, ProviderChatGenerator(provider_config))
        pipeline.connect("chat_prompt_builder.prompt", f"{component_name}.messages")

    return pipeline


def summarize_answers(result: dict[str, Any]) -> dict[str, Any]:
    answers = result["answer_builder"]["answers"]
    answer = answers[0]
    return {
        "answer": answer.data,
        "document_count": len(answer.documents or []),
        "llm_reply": result["llm"]["replies"][0],
        "llm_model": result["llm"]["meta"][0]["model"],
        "route": result["route_adapter"]["output"],
        "prompt_chars": len(result["prompt_builder"]["prompt"]),
    }


def summarize_provider_matrix(result: dict[str, Any]) -> dict[str, Any]:
    completions = {}
    for provider_name in PROVIDER_COMPLETION_CASES:
        component_name = f"{provider_name}_completion_llm"
        component_result = result[component_name]
        completions[provider_name] = {
            "reply": component_result["replies"][0],
            "provider": component_result["meta"][0]["provider"],
            "model": component_result["meta"][0]["model"],
            "usage": component_result["meta"][0]["usage"],
        }

    chats = {}
    for provider_name in PROVIDER_CHAT_CASES:
        component_name = f"{provider_name}_llm"
        component_result = result[component_name]
        reply = component_result["replies"][0]
        chats[provider_name] = {
            "reply": reply.text,
            "provider": component_result["meta"][0]["provider"],
            "model": component_result["meta"][0]["model"],
            "usage": component_result["meta"][0]["usage"],
        }

    return {
        "completion_providers": completions,
        "chat_providers": chats,
    }


@workflow(name="haystack_complex_edge_cases")
def run_complex_cases() -> dict[str, Any]:
    document_store = InMemoryDocumentStore(embedding_similarity_function="dot_product")

    indexing_pipeline = build_indexing_pipeline(document_store)
    indexing_pipeline.warm_up()
    indexing_result = indexing_pipeline.run(
        {},
        include_outputs_from={
            "document_source",
            "document_cleaner",
            "document_splitter",
            "document_embedder",
            "document_writer",
        },
    )

    rag_pipeline = build_rag_pipeline(document_store)
    rag_pipeline.warm_up()
    question = (
        "Checkout latency is high while one region is unhealthy. "
        "What should the incident team do?"
    )
    rag_result = rag_pipeline.run(
        {
            "bm25_retriever": {"query": question},
            "query_embedder": {"query": question},
            "severity_router": {"service": "checkout", "severity": "high"},
            "payload_assembler": {"query": question},
            "prompt_builder": {"query": question},
            "answer_builder": {"query": question},
        },
        include_outputs_from={
            "bm25_retriever",
            "embedding_retriever",
            "document_joiner",
            "severity_router",
            "route_adapter",
            "payload_assembler",
            "prompt_builder",
            "llm",
            "answer_builder",
        },
    )

    router_pipeline = build_router_only_pipeline()
    router_result = router_pipeline.run(
        {
            "severity_router": {
                "severity": "critical",
                "incident_id": "INC-HAYSTACK-CRITICAL",
            }
        },
        include_outputs_from={"severity_router", "route_uppercase_adapter"},
    )

    provider_pipeline = build_provider_matrix_pipeline()
    provider_pipeline.warm_up()
    provider_components = {
        "completion_prompt_builder",
        "chat_prompt_builder",
        *(f"{provider}_completion_llm" for provider in PROVIDER_COMPLETION_CASES),
        *(f"{provider}_llm" for provider in PROVIDER_CHAT_CASES),
    }
    provider_matrix_result = provider_pipeline.run(
        {
            "completion_prompt_builder": {
                "question": question,
                "route": rag_result["route_adapter"]["output"],
            },
            "chat_prompt_builder": {
                "question": question,
                "route": rag_result["route_adapter"]["output"],
            },
        },
        include_outputs_from=provider_components,
    )

    direct_component = rag_pipeline.get_component("llm")
    direct_generator_result = direct_component.run(
        prompt="Direct component run to verify generator-shaped output translation."
    )

    summary = {
        "run_id": RUN_ID,
        "documents_in_store": document_store.count_documents(),
        "filtered_checkout_docs": len(
            document_store.filter_documents(
                filters={"field": "meta.service", "operator": "==", "value": "checkout"}
            )
        ),
        "indexing": {
            "documents_written": indexing_result["document_writer"][
                "documents_written"
            ],
            "split_count": len(indexing_result["document_splitter"]["documents"]),
        },
        "rag": summarize_answers(rag_result),
        "router": router_result,
        "provider_matrix": summarize_provider_matrix(provider_matrix_result),
        "direct_generator": direct_generator_result,
    }
    print_result("haystack_complex_summary", summary)
    return summary


if __name__ == "__main__":
    try:
        run_complex_cases()
    finally:
        respan.flush()
