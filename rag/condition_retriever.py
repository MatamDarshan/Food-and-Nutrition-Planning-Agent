"""
rag/condition_retriever.py
--------------------------
Read-only retrieval over the condition-specific FAISS index.

This module is intentionally additive: the original ICMR-NIN retriever and its
16-query benchmark are untouched.  Condition guidance is returned as cited,
distance-filtered excerpts so a future agent node (or hybrid retriever) can
combine it with the core knowledge base without weakening safety checks.
"""

from pathlib import Path
from typing import Optional

from rag.document_sources import normalise_condition
from rag.ingest import DEFAULT_CONDITION_INDEX_DIR
from rag.vector_store import load_vector_store

# Same normalised-L2 threshold as the core retriever: for unit vectors this is
# equivalent to cosine similarity >= 0.22.
MAX_CONDITION_DISTANCE = 1.25
NO_CONDITION_MATCH_NOTICE = (
    "No relevant condition-specific guidance was found in the reference library."
)

_STORE_CACHE: dict[str, object] = {}


def get_condition_store(index_dir: Optional[Path] = None):
    """Return the cached condition vector store, or ``None`` if unavailable.

    ``None`` is cached as well so a missing index does not re-trigger the
    embedding model on every call.
    """
    target = Path(index_dir) if index_dir is not None else DEFAULT_CONDITION_INDEX_DIR
    key = str(target.resolve())
    if key not in _STORE_CACHE:
        _STORE_CACHE[key] = load_vector_store(index_dir=target)
    return _STORE_CACHE[key]


def reset_condition_store_cache() -> None:
    """Clear the cached store (used by tests and after an index rebuild)."""
    _STORE_CACHE.clear()


def retrieve_condition_guidance(
    query: str,
    condition: Optional[str] = None,
    k: int = 3,
    max_distance: float = MAX_CONDITION_DISTANCE,
    index_dir: Optional[Path] = None,
) -> list[dict]:
    """Retrieve cited excerpts from the condition reference library.

    Args:
        query: Natural-language nutrition question.
        condition: Optional condition name; mapped to the canonical tag and used
            as an exact metadata filter when the tag is known.
        k: Maximum number of distinct chunks to return.
        max_distance: Normalised-L2 distance cutoff (lower is stricter).
        index_dir: Optional index override, primarily for tests.

    Returns:
        A list of dicts with ``text``, ``source``, ``page``, ``condition``,
        ``distance``, ``is_relevant`` and ``document`` keys.
    """
    store = get_condition_store(index_dir)
    if store is None or not str(query or "").strip():
        return []

    # FAISS applies the metadata filter while selecting from ``fetch_k``
    # candidates, so the pool must be wider than the requested result count.
    search_kwargs = {"k": max(k * 4, k), "fetch_k": max(k * 12, 48)}
    if condition:
        tag = normalise_condition(condition)
        if tag:
            search_kwargs["filter"] = {"condition": tag}

    try:
        candidates = store.similarity_search_with_score(query, **search_kwargs)
    except Exception as exc:
        print(f"[WARN] Condition retrieval failed: {exc}")
        return []

    results: list[dict] = []
    seen: set[str] = set()
    for doc, distance in candidates:
        score = float(distance)
        if score > max_distance:
            continue
        chunk_id = doc.metadata.get("chunk_id") or f"{doc.metadata.get('source')}_{doc.metadata.get('page')}"
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        results.append(
            {
                "document": doc,
                "text": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "page": doc.metadata.get("page", 1),
                "condition": doc.metadata.get("condition", "general"),
                "distance": score,
                "is_relevant": True,
            }
        )
        if len(results) >= k:
            break
    return results


def format_condition_guidance(excerpts: list[dict], header: str = "**Condition-specific guidance**") -> str:
    """Render retrieved excerpts into a compact, cited answer block."""
    if not excerpts:
        return NO_CONDITION_MATCH_NOTICE

    lines = [header, ""]
    for idx, item in enumerate(excerpts, start=1):
        text = " ".join(str(item["text"]).split())
        if len(text) > 420:
            text = text[:420].rsplit(" ", 1)[0] + "…"
        lines.append(
            f"{idx}. {text} "
            f"[Source: {item['source']}, Page {item['page']}, "
            f"Condition: {item['condition']}, Vector Distance: {item['distance']:.4f}]"
        )
    return "\n".join(lines)
