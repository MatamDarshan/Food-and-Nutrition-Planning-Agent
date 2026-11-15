"""
rag/retriever.py
----------------
Retrieval interface and LangChain tool for querying the nutrition knowledge base.
Provides dense vector similarity search with document source attribution.
"""

from typing import Optional
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.vectorstores import VectorStoreRetriever

from rag.vector_store import get_or_create_vector_store

_RETRIEVER_INSTANCE: Optional[VectorStoreRetriever] = None
# For normalized embeddings, L2 distance <= 1.2 corresponds to cosine similarity >= 0.28
MAX_RELEVANCE_DISTANCE = 1.25


def get_retriever(k: int = 3) -> VectorStoreRetriever:
    """Return a cached VectorStoreRetriever instance configured for top-k retrieval."""
    global _RETRIEVER_INSTANCE
    if _RETRIEVER_INSTANCE is None:
        vector_store = get_or_create_vector_store()
        _RETRIEVER_INSTANCE = vector_store.as_retriever(search_kwargs={"k": k})
    return _RETRIEVER_INSTANCE


def retrieve_relevant_documents(
    query: str,
    k: int = 3,
    max_distance: float = MAX_RELEVANCE_DISTANCE,
) -> list[Document]:
    """Retrieve top-k documents matching the query, filtering out irrelevant chunks by distance threshold."""
    vector_store = get_or_create_vector_store()
    results = vector_store.similarity_search_with_score(query, k=k)
    # Filter documents by semantic distance threshold
    return [doc for doc, score in results if score <= max_distance]


def format_retrieved_docs(docs: list[Document]) -> str:
    """Format retrieved Document chunks into a readable string with citations."""
    if not docs:
        return (
            "No relevant nutrition document sections were found in the ICMR-NIN knowledge base for this query. "
            "The query appears to be outside the scope of the available nutritional guidelines."
        )

    formatted_sections = []
    for idx, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "ICMR-NIN Guidelines")
        page = doc.metadata.get("page", 1)
        citation = f"[Source: {source}, Page {page}]"
        formatted_sections.append(
            f"--- Reference Excerpt {idx} {citation} ---\n{doc.page_content}\n"
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
    - ICMR-NIN food group recommendations and balanced diet principles.

    Args:
        query: Specific nutritional query, e.g. 'benefits of millets' or 'sources of dietary fiber'.

    Returns:
        Formatted text excerpts with exact source document names and page numbers.
        Returns a notice if no relevant document sections were found.
    """
    try:
        docs = retrieve_relevant_documents(query=query, k=3)
        return format_retrieved_docs(docs)
    except Exception as exc:
        return f"[ERROR] Failed to retrieve nutrition knowledge: {str(exc)}"
