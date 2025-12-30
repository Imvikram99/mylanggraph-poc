"""Shared embedding builders with offline fallbacks."""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Any, List, Optional

from rich.console import Console

try:  # pragma: no cover - optional dependency
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover
    OpenAIEmbeddings = None  # type: ignore

console = Console()


@dataclass
class LocalHashEmbeddings:
    """Deterministic hashing-based embedding fallback for offline mode."""

    dim: int = 512

    def embed_query(self, text: str) -> List[float]:
        return self._encode(text or "")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._encode(text) for text in texts]

    # ---------------- internal helpers ----------------
    def _encode(self, text: str) -> List[float]:
        vector = [0.0] * self.dim
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            idx = int(digest[:8], 16) % self.dim
            vector[idx] += 1.0
        return self._normalize(vector)

    def _normalize(self, vector: List[float]) -> List[float]:
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]


class FallbackEmbeddings:
    """Wrap a primary embedding provider and fall back to local hashing."""

    def __init__(self, primary: Optional[Any], fallback: LocalHashEmbeddings) -> None:
        self.primary = primary
        self.fallback = fallback
        self._primary_failed = primary is None

    def embed_query(self, text: str) -> List[float]:
        if not self._primary_failed:
            try:
                return self.primary.embed_query(text)
            except Exception as exc:  # pragma: no cover - network/runtime failure
                console.log(f"[yellow]Embedding call failed; using local fallback[/] {exc}")
                self._primary_failed = True
        return self.fallback.embed_query(text)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not self._primary_failed:
            try:
                return self.primary.embed_documents(texts)
            except Exception as exc:  # pragma: no cover
                console.log(f"[yellow]Embedding batch failed; using local fallback[/] {exc}")
                self._primary_failed = True
        return self.fallback.embed_documents(texts)


def build_embeddings(*, provider: Optional[str] = None, model: Optional[str] = None) -> Any:
    """Return an embedding client with consistent fallback behavior."""
    provider_name = (provider or os.getenv("EMBEDDING_PROVIDER", "openrouter")).lower()
    model_name = model or os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-large")
    dim = int(os.getenv("EMBEDDING_DIM", "512"))
    fallback = LocalHashEmbeddings(dim=dim)
    if provider_name in {"local", "hash", "offline"}:
        console.log("[green]Using local hash embeddings (offline mode).[/]")
        return fallback

    if OpenAIEmbeddings is None:
        console.log("[yellow]langchain_openai unavailable; falling back to local embeddings.[/]")
        return fallback

    kwargs: dict[str, Any] = {"model": model_name}
    default_headers: dict[str, str] = {}
    if provider_name == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        api_base = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
        referer = os.getenv("OPENROUTER_SITE_URL") or os.getenv("OPENROUTER_REFERER")
        title = os.getenv("OPENROUTER_APP_NAME") or os.getenv("OPENROUTER_TITLE")
        if referer:
            default_headers["HTTP-Referer"] = referer
        if title:
            default_headers["X-Title"] = title
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        api_base = os.getenv("OPENAI_API_BASE")

    if not api_key:
        console.log(f"[yellow]No API key for provider '{provider_name}'; using local embeddings.[/]")
        return fallback

    kwargs["openai_api_key"] = api_key
    if api_base:
        kwargs["openai_api_base"] = api_base
    if default_headers:
        kwargs["default_headers"] = default_headers

    try:
        primary = OpenAIEmbeddings(**kwargs)
        return FallbackEmbeddings(primary, fallback)
    except Exception as exc:  # pragma: no cover - init failure
        console.log(f"[yellow]Embedding client init failed; using local embeddings[/] {exc}")
        return fallback
