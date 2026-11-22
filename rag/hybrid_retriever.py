"""
rag/hybrid_retriever.py
-----------------------
Hybrid retrieval with reciprocal rank fusion (RRF).

Dense FAISS search finds semantic matches; BM25 finds exact terms such as RDA
values, food names and condition labels. The two ranked lists are fused with
RRF so neither modality has to be score-calibrated against the other.

The module is additive: existing retrievers and the 16-query benchmark are
untouched. It exposes both a plain Python function and a LangChain tool.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from langchain_core.documents import Document
from langchain_core.tools import tool

from core.citations import format_verification, verify_citations
from rag.condition_retriever import DEFAULT_CONDITION_INDEX_DIR  # re-exported path
from rag.document_sources import normalise_condition
from rag.retriever import (
    MAX_RELEVANCE_DISTANCE,
    clean_excerpt_text,
    compose_extractive_answer,
)
from rag.sparse_index import BM25Index
from rag.vector_store import DEFAULT_INDEX_DIR, load_vector_store

ALL_COLLECTIONS = ("core", "conditions")
DEFAULT_RRF_K = 60
DEFAULT_DENSE_K = 12
DEFAULT_BM25_K = 12
DEFAULT_RESULT_K = 5

_ASSET_CACHE: dict[str, tuple[object, Optional[BM25Index]]] = {}


def _index_dir(collection: str) -> Path:
    if collection == "core":
        return DEFAULT_INDEX_DIR
    if collection == "conditions":
        return DEFAULT_CONDITION_INDEX_DIR
    raise ValueError(
        f"Unknown collection {collection!r}. Expected one of {', '.join(ALL_COLLECTIONS)}."
    )


def _collection_assets(collection: str) -> tuple[object, Optional[BM25Index]]:
    """Load and cache the FAISS store plus its in-memory BM25 index."""
    if collection not in _ASSET_CACHE:
        store = load_vector_store(index_dir=_index_dir(collection))
        documents: list[Document] = []
        if store is not None:
            documents = list(store.docstore._dict.values())
        bm25 = BM25Index(documents) if documents else None
        _ASSET_CACHE[collection] = (store, bm25)
    return _ASSET_CACHE[collection]


def reset_hybrid_cache() -> None:
    """Drop cached stores/indexes (used by tests and after an index rebuild)."""
    _ASSET_CACHE.clear()


@dataclass
class HybridPassage:
    """A retrieved chunk with the evidence from both retrieval modalities."""

    text: str
    source: str
    page: int
    collection: str
    chunk_id: str
    condition: Optional[str] = None
    dense_distance: Optional[float] = None
    dense_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    bm25_rank: Optional[int] = None
    rrf_score: float = 0.0

    @classmethod
    def from_document(cls, doc: Document, collection: str) -> "HybridPassage":
        metadata = doc.metadata or {}
        return cls(
            text=doc.page_content,
            source=str(metadata.get("source", "unknown")),
            page=int(metadata.get("page", 1) or 1),
            collection=collection,
            chunk_id=str(
                metadata.get("chunk_id")
                or f"{metadata.get('source')}_{metadata.get('page')}_"
                f"{hashlib.md5(doc.page_content.encode('utf-8')).hexdigest()[:8]}"
            ),
            condition=metadata.get("condition"),
        )

    def citation(self) -> str:
        parts = [f"Source: {self.source}", f"Page {self.page}"]
        if self.condition:
            parts.append(f"Condition: {self.condition}")
        parts.append(f"Collection: {self.collection}")
        if self.rrf_score:
            parts.append(f"RRF: {self.rrf_score:.4f}")
        return "[" + ", ".join(parts) + "]"

    def as_dict(self) -> dict:
        """Return a passage dict compatible with :func:`verify_citations`."""
        return {
            "text": self.text,
            "source": self.source,
            "page": self.page,
            "condition": self.condition,
            "collection": self.collection,
            "chunk_id": self.chunk_id,
            "dense_distance": self.dense_distance,
            "bm25_score": self.bm25_score,
            "rrf_score": self.rrf_score,
        }


def _condition_matches(doc: Document, tag: str) -> bool:
    metadata = doc.metadata or {}
    if metadata.get("condition") == tag:
        return True
    conditions = metadata.get("conditions") or []
    return tag in conditions if isinstance(conditions, (list, tuple, set)) else False


def retrieve_hybrid(
    query: str,
    k: int = DEFAULT_RESULT_K,
    mode: str = "hybrid",
    condition: Optional[str] = None,
    collections: tuple[str, ...] = ALL_COLLECTIONS,
    dense_k: int = DEFAULT_DENSE_K,
    bm25_k: int = DEFAULT_BM25_K,
    rrf_k: int = DEFAULT_RRF_K,
    max_dense_distance: float = MAX_RELEVANCE_DISTANCE,
    min_bm25_score: float = 0.0,
    dense_weight: float = 1.0,
    bm25_weight: float = 1.0,
    require_dense_support: bool = True,
) -> list[HybridPassage]:
    """Retrieve passages using dense, lexical or fused ranking.

    Args:
        query: User question.
        k: Maximum number of passages to return.
        mode: ``"dense"``, ``"bm25"`` or ``"hybrid"`` (RRF).
        condition: Optional condition name used as a metadata filter.
        collections: Which persisted indexes to search.
        dense_k / bm25_k: Candidate pool size per modality and collection.
        rrf_k: RRF smoothing constant (standard value is 60).
        max_dense_distance: L2 cutoff for dense candidates.
        min_bm25_score: Minimum lexical score for BM25 candidates.
        dense_weight / bm25_weight: Relative weight of each ranked list.
        require_dense_support: In hybrid mode, discard lexical-only hits. BM25
            alone can score an unrelated chunk highly when a single query term
            (for example a year) appears in it; requiring a dense hit keeps
            out-of-domain questions cleanly rejected.

    Returns:
        Ranked :class:`HybridPassage` objects, best first.
    """
    if mode not in {"dense", "bm25", "hybrid"}:
        raise ValueError(f"Unknown retrieval mode {mode!r}; use dense, bm25 or hybrid.")
    if not str(query or "").strip() or k <= 0:
        return []

    tag = normalise_condition(condition) if condition else None
    candidates: dict[str, HybridPassage] = {}

    for collection in collections:
        store, bm25 = _collection_assets(collection)

        if mode in {"dense", "hybrid"} and store is not None:
            search_kwargs = {"k": dense_k}
            if tag and collection == "conditions":
                search_kwargs["filter"] = {"condition": tag}
            try:
                dense_hits = store.similarity_search_with_score(query, **search_kwargs)
            except Exception as exc:
                print(f"[WARN] Dense retrieval failed for {collection}: {exc}")
                dense_hits = []
            for rank, (doc, distance) in enumerate(dense_hits, start=1):
                score = float(distance)
                if score > max_dense_distance:
                    continue
                if tag and collection == "conditions" and not _condition_matches(doc, tag):
                    continue
                passage = HybridPassage.from_document(doc, collection)
                passage.dense_distance = score
                passage.dense_rank = rank
                candidates.setdefault(passage.chunk_id, passage)

        if mode in {"bm25", "hybrid"} and bm25 is not None:
            try:
                lexical_hits = bm25.search_with_rank(query, k=bm25_k)
            except Exception as exc:
                print(f"[WARN] BM25 retrieval failed for {collection}: {exc}")
                lexical_hits = []
            for doc, score, rank in lexical_hits:
                if score < min_bm25_score:
                    continue
                if tag and not _condition_matches(doc, tag):
                    continue
                passage = HybridPassage.from_document(doc, collection)
                if passage.chunk_id in candidates:
                    existing = candidates[passage.chunk_id]
                    passage = existing
                if passage.bm25_rank is None:
                    passage.bm25_score = float(score)
                    passage.bm25_rank = rank
                    candidates[passage.chunk_id] = passage

    if mode == "dense":
        ranked = sorted(
            (p for p in candidates.values() if p.dense_rank is not None),
            key=lambda p: (p.dense_rank or 0, p.dense_distance or 0.0),
        )
    elif mode == "bm25":
        ranked = sorted(
            (p for p in candidates.values() if p.bm25_rank is not None),
            key=lambda p: (p.bm25_rank or 0, -(p.bm25_score or 0.0)),
        )
    else:
        for passage in candidates.values():
            score = 0.0
            if passage.dense_rank is not None:
                score += dense_weight / (rrf_k + passage.dense_rank)
            if passage.bm25_rank is not None:
                score += bm25_weight / (rrf_k + passage.bm25_rank)
            passage.rrf_score = score
        ranked = sorted(
            candidates.values(),
            key=lambda p: (
                -p.rrf_score,
                p.dense_distance if p.dense_distance is not None else float("inf"),
                p.source,
                p.page,
            ),
        )
        if require_dense_support:
            ranked = [p for p in ranked if p.dense_rank is not None]

    return ranked[:k]


@tool
def retrieve_hybrid_nutrition_knowledge(query: str, condition: str = "") -> str:
    """Search ICMR-NIN and condition guidelines with dense + BM25 hybrid retrieval.

    Returns a cited answer plus a deterministic citation verification result.
    Pass a health condition such as 'PCOS' or 'thyroid' to narrow the evidence.
    """
    passages = retrieve_hybrid(query, condition=condition or None)
    if not passages:
        return (
            "No relevant nutrition document sections were found in the hybrid "
            "knowledge base for this query."
        )

    cleaned_texts = [clean_excerpt_text(passage.text) for passage in passages]
    answer = compose_extractive_answer(query, cleaned_texts)
    lines = ["**Answer (hybrid retrieval)**", answer or "No extractive answer could be composed.", ""]
    lines.append("**Supporting excerpts**")
    for idx, passage in enumerate(passages, start=1):
        excerpt = " ".join(cleaned_texts[idx - 1].split())
        if len(excerpt) > 420:
            excerpt = excerpt[:420].rsplit(" ", 1)[0] + "…"
        lines.append(f"{idx}. {excerpt} {passage.citation()}")

    lines.extend(["", "**Sources**"])
    lines.extend(f"- {passage.citation()}" for passage in passages)

    evidence = [
        dict(passage.as_dict(), text=cleaned_texts[idx])
        for idx, passage in enumerate(passages)
    ]
    report = verify_citations("\n".join(lines), evidence)
    lines.extend(["", format_verification(report)])
    return "\n".join(lines)
