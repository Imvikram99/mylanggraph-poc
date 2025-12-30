"""Utility helpers for retrieving documents from the configured vector store."""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console

try:  # pragma: no cover - optional dependency
    from langchain_community.vectorstores import Chroma
except Exception:  # pragma: no cover
    Chroma = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest
except Exception:  # pragma: no cover
    QdrantClient = None  # type: ignore[assignment]
    rest = None  # type: ignore

from .embeddings import build_embeddings

console = Console()


@dataclass
class RetrievedDocument:
    """Wrapper for retrieved context used inside the graph."""

    text: str
    metadata: Dict[str, Any]
    score: float = 0.0


class VectorStoreRetriever:
    """Best-effort retriever that prefers Qdrant, then Chroma, then files."""

    def __init__(
        self,
        *,
        collection: Optional[str] = None,
        persist_dir: Optional[str] = None,
        docs_root: Optional[str] = None,
        top_k: Optional[int] = None,
    ) -> None:
        self.vector_impl = os.getenv("VECTOR_DB_IMPL", "qdrant").lower()
        self.collection = collection or os.getenv("QDRANT_COLLECTION", "langgraph_memories")
        self.persist_dir = persist_dir or os.getenv("VECTOR_DB_PATH", "data/memory/vectorstore")
        self.docs_root = Path(docs_root or os.getenv("KNOWLEDGE_BASE_PATH", "data/knowledge_base"))
        self.qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.qdrant_api_key = os.getenv("QDRANT_API_KEY") or None
        self.top_k = top_k or int(os.getenv("RETRIEVAL_TOP_K", os.getenv("MEMORY_TOP_K", "6")))
        self._client = self._build_qdrant_client() if self.vector_impl == "qdrant" else None
        self._embeddings = self._build_embeddings()

    def search(self, query: str, *, top_k: Optional[int] = None) -> List[RetrievedDocument]:
        """Return a list of retrieved documents ordered by score."""
        query = (query or "").strip()
        if not query:
            return []
        limit = top_k or self.top_k
        if self.vector_impl == "qdrant" and self._client and self._embeddings:
            try:
                return self._search_qdrant(query, limit)
            except Exception as exc:  # pragma: no cover - remote service failure
                console.log(f"[red]Qdrant search failed[/] {exc}; falling back to filesystem.")
        if self.vector_impl == "chroma" and Chroma is not None and self._embeddings:
            try:
                return self._search_chroma(query, limit)
            except Exception as exc:  # pragma: no cover
                console.log(f"[red]Chroma search failed[/] {exc}; falling back to filesystem.")
        return self._search_filesystem(query, limit)

    # ---------------- private helpers ----------------
    def _build_embeddings(self):
        try:
            return build_embeddings()
        except Exception as exc:  # pragma: no cover - builder failure
            console.log(f"[yellow]Embedding builder failed; falling back to keyword search[/] {exc}")
            return None

    def _build_qdrant_client(self) -> Optional[QdrantClient]:
        if QdrantClient is None:
            return None
        try:
            return QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
        except Exception as exc:  # pragma: no cover - qdrant not accessible
            console.log(f"[yellow]Unable to reach Qdrant[/] {exc}")
            return None

    def _search_qdrant(self, query: str, top_k: int) -> List[RetrievedDocument]:
        assert self._client is not None and self._embeddings is not None and rest is not None
        vector = self._embeddings.embed_query(query)
        result = self._query_qdrant_points(vector, top_k)
        docs: List[RetrievedDocument] = []
        for point in result:
            payload = point.payload or {}
            docs.append(
                RetrievedDocument(
                    text=str(payload.get("text") or payload.get("chunk") or ""),
                    metadata=payload,
                    score=float(point.score or 0.0),
                )
            )
        return docs

    def _query_qdrant_points(self, vector, top_k: int):
        """Call whichever Qdrant search API is available (search/query_points)."""
        assert self._client is not None
        search_kwargs = {
            "collection_name": self.collection,
            "limit": top_k,
            "with_payload": True,
        }
        if hasattr(self._client, "search"):
            try:
                return self._client.search(query_vector=vector, **search_kwargs)
            except AttributeError:
                # Older/newer qdrant-client builds may not expose .search
                pass
        # qdrant-client>=1.10 exposes query_points, while older releases use search_points
        if hasattr(self._client, "search_points"):
            response = self._client.search_points(query=vector, **search_kwargs)
            return getattr(response, "points", response)
        if hasattr(self._client, "query_points"):
            response = self._client.query_points(query=vector, **search_kwargs)
            return getattr(response, "points", response)
        raise AttributeError("Qdrant client has no supported search method")

    def _search_chroma(self, query: str, top_k: int) -> List[RetrievedDocument]:
        assert Chroma is not None and self._embeddings is not None
        store = Chroma(
            collection_name=self.collection,
            embedding_function=self._embeddings,
            persist_directory=self.persist_dir,
        )
        result = store.similarity_search_with_relevance_scores(query, k=top_k)
        docs: List[RetrievedDocument] = []
        for doc, score in result:
            docs.append(
                RetrievedDocument(
                    text=doc.page_content,
                    metadata=doc.metadata,
                    score=float(score),
                )
            )
        return docs

    def _search_filesystem(self, query: str, top_k: int) -> List[RetrievedDocument]:
        if not self.docs_root.exists():
            return []
        keywords = set(query.lower().split())
        scored: List[RetrievedDocument] = []
        for path in sorted(self.docs_root.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            tokens = set(text.lower().split())
            overlap = len(tokens.intersection(keywords))
            if overlap == 0:
                continue
            snippet = self._build_snippet(text)
            scored.append(
                RetrievedDocument(
                    text=snippet,
                    metadata={"source": path.name, "path": str(path)},
                    score=float(overlap),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:top_k]

    @staticmethod
    def _build_snippet(text: str, limit: int = 500) -> str:
        text = " ".join(text.split())
        return text[:limit] + ("…" if len(text) > limit else "")
