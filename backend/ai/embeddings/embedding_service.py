"""
LogSage AI — Embedding Service
SentenceTransformers embeddings + ChromaDB vector store.
Supports batch processing and similarity search.
"""

from __future__ import annotations

import asyncio
import hashlib
from functools import lru_cache
from typing import TYPE_CHECKING

import chromadb
import numpy as np
import structlog
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from core.config import settings

if TYPE_CHECKING:
    from models.models import LogEntry

logger = structlog.get_logger(__name__)

COLLECTION_LOGS = "log_entries"
COLLECTION_INCIDENTS = "incidents"


# ── Model singleton ───────────────────────────────────────────────────────────

_model: SentenceTransformer | None = None
_model_lock = asyncio.Lock()


async def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        async with _model_lock:
            if _model is None:
                logger.info("Loading embedding model", model=settings.EMBEDDING_MODEL)
                loop = asyncio.get_event_loop()
                _model = await loop.run_in_executor(
                    None,
                    lambda: SentenceTransformer(settings.EMBEDDING_MODEL),
                )
                logger.info("Embedding model loaded")
    return _model


# ── ChromaDB client ───────────────────────────────────────────────────────────

_chroma_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info("ChromaDB client initialized", path=settings.CHROMA_PERSIST_DIR)
    return _chroma_client


def get_collection(name: str) -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


# ── Core embedding operations ─────────────────────────────────────────────────

async def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts → float32 array [N, D]."""
    if not texts:
        return np.array([])
    model = await get_embedding_model()
    loop = asyncio.get_event_loop()
    vectors = await loop.run_in_executor(
        None,
        lambda: model.encode(
            texts,
            batch_size=settings.BATCH_EMBEDDING_SIZE,
            normalize_embeddings=True,
            show_progress_bar=False,
        ),
    )
    return vectors.astype(np.float32)


async def embed_single(text: str) -> np.ndarray:
    vectors = await embed_texts([text])
    return vectors[0]


def _make_chroma_id(log_id: str) -> str:
    """Stable ChromaDB document ID from log entry ID."""
    return hashlib.sha256(log_id.encode()).hexdigest()[:32]


# ── Log entry embedding ───────────────────────────────────────────────────────

async def embed_log_entries(
    entries: list["LogEntry"],
) -> dict[str, list[float]]:
    """
    Embed log entries and upsert to ChromaDB.
    Returns mapping: log_entry.id → embedding vector.
    """
    if not entries:
        return {}

    texts = [f"[{e.level}] {e.service or 'unknown'}: {e.message}" for e in entries]
    vectors = await embed_texts(texts)

    collection = get_collection(COLLECTION_LOGS)

    chroma_ids = [_make_chroma_id(e.id) for e in entries]
    metadatas = [
        {
            "log_id": e.id,
            "session_id": e.session_id,
            "level": str(e.level),
            "service": e.service or "",
            "timestamp": e.timestamp.isoformat(),
        }
        for e in entries
    ]

    # Upsert in batches of 500 (Chroma limit)
    batch_size = 500
    for i in range(0, len(entries), batch_size):
        batch_slice = slice(i, i + batch_size)
        collection.upsert(
            ids=chroma_ids[batch_slice],
            embeddings=vectors[batch_slice].tolist(),
            documents=texts[batch_slice],
            metadatas=metadatas[batch_slice],
        )

    logger.info("Embedded log entries", count=len(entries))
    return {e.id: vectors[i].tolist() for i, e in enumerate(entries)}


async def embed_incident(
    incident_id: str,
    text: str,
    metadata: dict | None = None,
) -> list[float]:
    """Embed an incident summary for RAG retrieval."""
    vector = await embed_single(text)
    collection = get_collection(COLLECTION_INCIDENTS)
    collection.upsert(
        ids=[incident_id],
        embeddings=[vector.tolist()],
        documents=[text],
        metadatas=[metadata or {}],
    )
    return vector.tolist()


# ── Similarity search ─────────────────────────────────────────────────────────

async def find_similar_logs(
    query: str,
    top_k: int = 20,
    level_filter: str | None = None,
    service_filter: str | None = None,
) -> list[dict]:
    """
    Similarity search over log embeddings.
    Returns list of {log_id, distance, document, metadata}.
    """
    query_vec = await embed_single(query)
    collection = get_collection(COLLECTION_LOGS)

    where: dict | None = None
    if level_filter or service_filter:
        conditions = []
        if level_filter:
            conditions.append({"level": {"$eq": level_filter}})
        if service_filter:
            conditions.append({"service": {"$eq": service_filter}})
        where = {"$and": conditions} if len(conditions) > 1 else conditions[0]

    kwargs: dict = dict(
        query_embeddings=[query_vec.tolist()],
        n_results=min(top_k, collection.count() or 1),
        include=["documents", "metadatas", "distances"],
    )
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)

    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        output.append(
            {
                "chroma_id": doc_id,
                "log_id": results["metadatas"][0][i].get("log_id"),
                "distance": results["distances"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
            }
        )
    return output


async def find_similar_incidents(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """RAG retrieval: find past incidents similar to query."""
    query_vec = await embed_single(query)
    collection = get_collection(COLLECTION_INCIDENTS)

    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_embeddings=[query_vec.tolist()],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )

    output = []
    for i, doc_id in enumerate(results["ids"][0]):
        output.append(
            {
                "incident_id": doc_id,
                "distance": results["distances"][0][i],
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
            }
        )
    return output


# ── Clustering support ────────────────────────────────────────────────────────

async def get_embeddings_for_ids(log_ids: list[str]) -> dict[str, list[float]]:
    """Fetch stored embeddings for given log IDs."""
    chroma_ids = [_make_chroma_id(lid) for lid in log_ids]
    collection = get_collection(COLLECTION_LOGS)

    try:
        results = collection.get(
            ids=chroma_ids,
            include=["embeddings", "metadatas"],
        )
    except Exception:
        return {}

    output = {}
    for i, chroma_id in enumerate(results["ids"]):
        meta = results["metadatas"][i]
        log_id = meta.get("log_id")
        if log_id and results["embeddings"]:
            output[log_id] = results["embeddings"][i]
    return output


async def compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
