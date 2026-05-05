"""Shared setup helpers for the CrewAI tracing examples."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str


def load_env() -> None:
    current_dir = Path(__file__).resolve().parent
    candidates = [
        current_dir / ".env",
        current_dir.parents[2] / ".env",
        current_dir.parents[3] / "respan" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=True)
            break
    else:
        load_dotenv(override=True)

    os.environ.setdefault("XDG_DATA_HOME", "/tmp/respan-crewai-data")
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "true")


def configure_environment() -> Settings:
    load_env()
    settings = Settings(
        api_key=os.environ["RESPAN_API_KEY"],
        base_url=os.getenv("RESPAN_BASE_URL", "https://api.respan.ai/api"),
        model=os.getenv("RESPAN_MODEL", "gpt-4o-mini"),
    )
    os.environ["OPENAI_API_KEY"] = settings.api_key
    os.environ["OPENAI_BASE_URL"] = settings.base_url
    return settings


def start_respan(app_name: str, metadata: dict[str, Any] | None = None) -> tuple[Settings, Any]:
    settings = configure_environment()

    from respan import Respan
    from respan_instrumentation_crewai import CrewAIInstrumentor

    respan = Respan(
        app_name=app_name,
        api_key=settings.api_key,
        base_url=settings.base_url,
        instrumentations=[CrewAIInstrumentor()],
        metadata=metadata or {"example": app_name},
    )
    return settings, respan


def print_raw_result(title: str, result: Any) -> None:
    print(f"\n=== {title} ===")
    print(getattr(result, "raw", result))
