"""
rag/retriever.py
----------------
Retrieval interface and LangChain tool for querying the nutrition knowledge base.
Provides dense vector similarity search with document source attribution.
"""

from typing import Any, Optional, Union
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.vectorstores import VectorStoreRetriever

from rag.vector_store import get_or_create_vector_store

_RETRIEVER_INSTANCE: Optional[VectorStoreRetriever] = None

# Euclidean (L2) distance threshold for normalized 384-dimensional embeddings.
# For unit vectors, squared Euclidean distance d^2 = 2 * (1 - cosine_similarity).
# A threshold of 1.25 corresponds to cosine similarity >= 0.22.
# Distance values represent metric vector space distance and must not be interpreted as probabilities or percentages.
MAX_RELEVANCE_DISTANCE = 1.25


def get_retriever(k: int = 3) -> VectorStoreRetriever:
    """Return a cached VectorStoreRetriever instance configured for top-k retrieval."""
    global _RETRIEVER_INSTANCE
    if _RETRIEVER_INSTANCE is None:
        vector_store = get_or_create_vector_store()
        _RETRIEVER_INSTANCE = vector_store.as_retriever(search_kwargs={"k": k})
    return _RETRIEVER_INSTANCE


def retrieve_relevant_chunks(
    query: str,
    k: int = 3,
    max_distance: float = MAX_RELEVANCE_DISTANCE,
) -> list[tuple[Document, float]]:
    """Retrieve top-k document chunks and their Euclidean vector distances, filtered by threshold."""
    vector_store = get_or_create_vector_store()
    results = vector_store.similarity_search_with_score(query, k=k)
    return [(doc, float(score)) for doc, score in results if score <= max_distance]


def retrieve_relevant_documents(
    query: str,
    k: int = 3,
    max_distance: float = MAX_RELEVANCE_DISTANCE,
) -> list[Document]:
    """Retrieve top-k documents matching the query, filtering out irrelevant chunks by distance threshold."""
    chunks_with_scores = retrieve_relevant_chunks(query=query, k=k, max_distance=max_distance)
    return [doc for doc, _ in chunks_with_scores]


def retrieve_with_details(
    query: str,
    k: int = 3,
    max_distance: float = MAX_RELEVANCE_DISTANCE,
) -> list[dict[str, Any]]:
    """Retrieve detailed metadata and vector distances for evaluation and inspection."""
    vector_store = get_or_create_vector_store()
    results = vector_store.similarity_search_with_score(query, k=k)
    details = []
    for doc, score in results:
        dist = float(score)
        details.append({
            "document": doc.metadata.get("source", "ICMR-NIN Guidelines"),
            "page": doc.metadata.get("page", 1),
            "chunk_id": doc.metadata.get("chunk_id", ""),
            "distance": round(dist, 4),
            "is_relevant": dist <= max_distance,
            "text": doc.page_content.strip(),
        })
    return details


def format_retrieved_docs(
    docs_or_tuples: Union[list[Document], list[tuple[Document, float]]],
) -> str:
    """Format retrieved Document chunks and vector distances into a clear, cited string.

    Avoids treating distance as a probability or confidence percentage.
    """
    if not docs_or_tuples:
        return (
            "No relevant nutrition document sections were found in the ICMR-NIN knowledge base for this query. "
            "The knowledge base does not contain sufficient information on this specific topic."
        )

    formatted_sections = []
    for idx, item in enumerate(docs_or_tuples, 1):
        if isinstance(item, tuple):
            doc, dist = item
            dist_str = f" (Vector Distance: {dist:.4f})"
        else:
            doc = item
            dist_str = ""

        source = doc.metadata.get("source", "ICMR-NIN Guidelines")
        page = doc.metadata.get("page", 1)
        citation = f"[Source: {source}, Page {page}]"
        formatted_sections.append(
            f"--- Reference Excerpt {idx} {citation}{dist_str} ---\n{doc.page_content.strip()}\n"
        )

    return "\n".join(formatted_sections)


@tool
def retrieve_nutrition_knowledge(query: str) -> str:
    """Retrieve authoritative scientific nutrition knowledge and guidelines from ICMR-NIN documents.

    Use this tool to answer conceptual or educational dietary questions, such as:
    - Nutritional benefits and therapeutic properties of millets (ragi, bajra, jowar).
    - Top Indian sources of dietary protein and cereal-pulse amino acid synergy.
    - The biological importance, daily requirements, and types of dietary fiber.
    - Anatomical and nutritional differences between whole grains and refined grains.
    - Micronutrient requirements (Calcium, Iron, Vitamin B12) and bioavailability.
    - Healthy dietary fats, cooking oils balance (SFA/MUFA/PUFA), and trans fat elimination.
    - Carbohydrate quality, energy contribution (50-55%), and food synergies.

    Args:
        query: Specific nutritional query, e.g. 'benefits of millets' or 'sources of dietary fiber'.

    Returns:
        Formatted text excerpts with exact source document names, page numbers, and retrieved passages.
        Returns a notice if the knowledge base does not contain sufficient information.
    """
    try:
        chunks_with_scores = retrieve_relevant_chunks(query=query, k=3)
        return format_retrieved_docs(chunks_with_scores)
    except Exception as exc:
        return f"[ERROR] Failed to retrieve nutrition knowledge: {str(exc)}"
