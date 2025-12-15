"""Temporal memory backed by Qdrant (with local fallback)."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
except Exception:  # pragma: no cover - optional dependency
    QdrantClient = None  # type: ignore[assignment]
    rest = None  # type: ignore

try:
    from langchain_openai import OpenAIEmbeddings
except Exception:  # pragma: no cover
    OpenAIEmbeddings = None  # type: ignore

console = Console()


@dataclass
class MemoryRecord:
    """Structured memory item."""

    text: str
    category: str = "general"
    importance: float = 0.5
    source: str = "agent"
    timestamp: datetime = datetime.now(timezone.utc)
    metadata: Optional[Dict[str, Any]] = None


class TemporalMemoryStore:
    """Persist time-aware memories."""

    def __init__(self) -> None:
        self.vector_impl = os.getenv("VECTOR_DB_IMPL", "qdrant").lower()
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY")
        self.collection = os.getenv("QDRANT_COLLECTION", "langgraph_memories")
        self.local_path = Path(os.getenv("VECTOR_DB_PATH", "data/memory/vectorstore") + "/memories.jsonl")
        self.local_path.parent.mkdir(parents=True, exist_ok=True)
        self.top_k = int(os.getenv("MEMORY_TOP_K", "8"))
        self.time_window_days = int(os.getenv("MEMORY_TIME_WINDOW_DAYS", "30"))
        self.half_life_hours = float(os.getenv("MEMORY_DECAY_HALF_LIFE_HOURS", "72"))
        self.ttl_task_days = int(os.getenv("MEMORY_TTL_TASK_DAYS", "7"))
        self.enabled = self.vector_impl == "qdrant" and QdrantClient is not None
        self._client = self._build_client() if self.enabled else None
        self._embeddings = self._build_embeddings()

    def _build_client(self) -> Optional[QdrantClient]:
        if QdrantClient is None:
            return None
        client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key or None)
        try:
            client.get_collection(self.collection)
        except Exception:
            console.log(f"[yellow]Creating Qdrant collection '{self.collection}'[/]")
            client.recreate_collection(
                self.collection,
                vectors_config=rest.VectorParams(size=1536, distance=rest.Distance.COSINE),  # type: ignore[arg-type]
            )
        return client

    def _build_embeddings(self):
        if OpenAIEmbeddings is None:
            return None
        provider = os.getenv("EMBEDDING_PROVIDER", "openrouter").lower()
        model = os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-large")
        if provider == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
            api_base = os.getenv("OPENROUTER_BASE", "https://openrouter.ai/api/v1")
        else:
            api_key = os.getenv("OPENAI_API_KEY")
            api_base = os.getenv("OPENAI_API_BASE")
        if not api_key:
            console.log("[yellow]No embedding API key configured; falling back to keyword similarity[/]")
            return None
        kwargs = {"model": model, "openai_api_key": api_key}
        if api_base:
            kwargs["openai_api_base"] = api_base
        try:
            return OpenAIEmbeddings(**kwargs)
        except Exception as exc:
            console.log(f"[yellow]Embedding client init failed ({exc}); using keyword similarity[/]")
            return None

    # --------------------- write ---------------------
    def write(self, record: MemoryRecord) -> str:
        """Store a new memory."""
        if self.enabled and self._client and self._embeddings:
            return self._write_qdrant(record)
        return self._write_local(record)

    def _write_qdrant(self, record: MemoryRecord) -> str:
        assert self._client is not None and rest is not None
        payload = self._payload(record)
        vector = self._embeddings.embed_query(record.text) if self._embeddings else [0.0] * 1536
        point_id = str(uuid.uuid4())
        self._client.upsert(
            collection_name=self.collection,
            points=[rest.PointStruct(id=point_id, vector=vector, payload=payload)],  # type: ignore[arg-type]
        )
        return point_id

    def _write_local(self, record: MemoryRecord) -> str:
        payload = self._payload(record)
        payload["id"] = str(uuid.uuid4())
        with self.local_path.open("a", encoding="utf-8") as fout:
            fout.write(json.dumps(payload) + "\n")
        return payload["id"]

    def _payload(self, record: MemoryRecord) -> Dict[str, Any]:
        return {
            "text": record.text,
            "category": record.category,
            "importance": record.importance,
            "source": record.source,
            "ts": record.timestamp.isoformat(),
            "metadata": record.metadata or {},
        }

    # --------------------- search ---------------------
    def search(self, query: str, *, time_window_days: Optional[int] = None, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        if self.enabled and self._client and self._embeddings:
            return self._search_qdrant(query, time_window_days, top_k)
        return self._search_local(query, time_window_days, top_k)

    def _search_qdrant(self, query: str, time_window_days: Optional[int], top_k: Optional[int]) -> List[Dict[str, Any]]:
        assert self._client is not None and rest is not None
        vector = self._embeddings.embed_query(query) if self._embeddings else [0.0] * 1536
        now = datetime.now(timezone.utc)
        since = now - timedelta(days=time_window_days or self.time_window_days)
        conditions = [
            rest.FieldCondition(
                key="ts",
                range=rest.Range(gte=since.isoformat()),
            )
        ]
        search_result = self._client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k or self.top_k,
            query_filter=rest.Filter(must=conditions),
            with_payload=True,
        )
        scored = []
        for point in search_result:
            payload = point.payload or {}
            ts_str = payload.get("ts", datetime.now(timezone.utc).isoformat())
            ts = datetime.fromisoformat(ts_str)
            recency_bonus = self._recency_bonus(ts)
            final_score = (point.score or 0.0) + recency_bonus + float(payload.get("importance", 0))
            payload.update({"score": final_score})
            scored.append(payload)
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored

    def _search_local(self, query: str, time_window_days: Optional[int], top_k: Optional[int]) -> List[Dict[str, Any]]:
        if not self.local_path.exists():
            return []
        with self.local_path.open("r", encoding="utf-8") as fin:
            rows = [json.loads(line) for line in fin if line.strip()]
        since = datetime.now(timezone.utc) - timedelta(days=time_window_days or self.time_window_days)
        filtered = [row for row in rows if datetime.fromisoformat(row["ts"]) >= since]
        # naive string similarity by counting shared tokens
        query_tokens = set(query.lower().split())
        scored = []
        for row in filtered:
            text_tokens = set(row["text"].lower().split())
            overlap = len(query_tokens.intersection(text_tokens))
            ts = datetime.fromisoformat(row["ts"])
            row["score"] = overlap + self._recency_bonus(ts) + float(row.get("importance", 0))
            scored.append(row)
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[: top_k or self.top_k]

    def prune(self) -> None:
        """Remove expired task_state entries from local cache."""
        if not self.local_path.exists():
            return
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_task_days)
        rows = []
        with self.local_path.open("r", encoding="utf-8") as fin:
            for line in fin:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("category") == "task_state":
                    ts = datetime.fromisoformat(row["ts"])
                    if ts < cutoff:
                        continue
                rows.append(row)
        with self.local_path.open("w", encoding="utf-8") as fout:
            for row in rows:
                fout.write(json.dumps(row) + "\n")

    def _recency_bonus(self, timestamp: datetime) -> float:
        now = datetime.now(timezone.utc)
        delta_hours = max(0.0, (now - timestamp).total_seconds() / 3600)
        half_life = self.half_life_hours or 48.0
        decay = 0.693 / half_life
        return float(os.getenv("MEMORY_DECAY_ALPHA", "0.5")) * pow(2.71828, -decay * delta_hours)


def scrub_text(text: str) -> str:
    """Basic scrubbing when SCRUB_TRAJECTORIES=true."""
    if os.getenv("SCRUB_TRAJECTORIES", "false").lower() != "true":
        return text
    return "[redacted]" if len(text) > 32 else text
