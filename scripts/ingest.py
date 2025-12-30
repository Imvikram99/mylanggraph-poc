"""Document ingestion CLI."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

import typer
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from src.services.embeddings import build_embeddings

app = typer.Typer(help="Ingest documents into the selected vector store.")


@app.command()
def run(
    docs: Path = typer.Option(
        Path("data/knowledge_base"),
        "--docs",
        "-d",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Directory of documents to ingest",
    ),
    glob: str = typer.Option("**/*.md", help="Glob filter for docs"),
    collection: Optional[str] = typer.Option(None, help="Override Qdrant collection name"),
) -> None:
    """Load local docs and push them to Qdrant (default) or Chroma fallback."""
    load_dotenv()
    documents = _load_documents(docs, glob)
    if not documents:
        typer.secho("No documents found for ingestion.", fg=typer.colors.YELLOW)
        raise typer.Exit(0)
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=50)
    splits = splitter.split_documents(documents)
    typer.echo(f"Ingesting {len(splits)} chunks from {docs}")
    embeddings = _build_embeddings()
    vector_impl = os.getenv("VECTOR_DB_IMPL", "qdrant").lower()
    if vector_impl == "qdrant":
        _persist_qdrant(splits, embeddings, collection)
    else:
        _persist_chroma(splits, embeddings)


def _load_documents(root: Path, glob: str):
    loader = DirectoryLoader(str(root), glob=glob, loader_cls=TextLoader, loader_kwargs={"encoding": "utf-8"})
    return loader.load()


def _persist_qdrant(documents, embeddings, collection_override: Optional[str]) -> None:
    client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333"), api_key=os.getenv("QDRANT_API_KEY") or None)
    collection_name = collection_override or os.getenv("QDRANT_COLLECTION", "langgraph_memories")
    expected_dim = int(os.getenv("EMBEDDING_DIM", "3072"))
    _ensure_collection(client, collection_name, expected_dim)
    vectors = [embeddings.embed_query(doc.page_content) for doc in documents]
    payloads = [
        {
            "text": doc.page_content,
            "source": doc.metadata.get("source"),
            "ts": doc.metadata.get("ts") or datetime.now(timezone.utc).isoformat(),
            "ts_epoch": doc.metadata.get("ts_epoch") or time.time(),
        }
        for doc in documents
    ]
    client.upsert(
        collection_name=collection_name,
        points=[
            rest.PointStruct(id=i, vector=vectors[i], payload=payloads[i])
            for i in range(len(documents))
        ],
    )
    typer.echo(f"Uploaded {len(documents)} vectors to Qdrant collection '{collection_name}'.")


def _persist_chroma(documents, embeddings) -> None:
    from langchain_community.vectorstores import Chroma

    persist_dir = os.getenv("VECTOR_DB_PATH", "data/memory/vectorstore")
    collection_name = os.getenv("QDRANT_COLLECTION", "langgraph_memories")
    Chroma.from_documents(
        documents,
        embeddings,
        persist_directory=persist_dir,
        collection_name=collection_name,
    )
    typer.echo(f"Persisted {len(documents)} chunks to Chroma at {persist_dir} (collection={collection_name}).")


def _build_embeddings():
    return build_embeddings()


def _ensure_collection(client: QdrantClient, name: str, dim: int) -> None:
    def create():
        client.create_collection(
            name,
            vectors_config=rest.VectorParams(size=dim, distance=rest.Distance.COSINE),
        )

    if not client.collection_exists(name):
        create()
        return

    info = client.get_collection(name)
    current_dim = getattr(getattr(info.config.params, "vectors", None), "size", None)
    if current_dim and current_dim != dim:
        typer.secho(f"Vector dim mismatch ({current_dim}!={dim}); recreating collection '{name}'.", fg=typer.colors.YELLOW)
        client.delete_collection(name)
        create()


if __name__ == "__main__":
    app()
