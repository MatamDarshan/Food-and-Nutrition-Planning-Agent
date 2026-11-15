"""
rag/text_splitter.py
--------------------
Splits extracted nutrition documents into meaningful, overlapping chunks
suitable for dense semantic embedding and retrieval.
"""

from typing import Optional
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 120


def get_text_splitter(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> RecursiveCharacterTextSplitter:
    """Instantiate a RecursiveCharacterTextSplitter configured for nutrition texts."""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "•", ". ", " ", ""],
        length_function=len,
    )


def split_nutrition_documents(
    documents: list[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Split input documents into chunked Document objects with unique chunk_id metadata."""
    if not documents:
        return []

    splitter = get_text_splitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    chunks = splitter.split_documents(documents)

    # Attach unique chunk_id to each chunk
    for idx, chunk in enumerate(chunks):
        source = chunk.metadata.get("source", "doc")
        page = chunk.metadata.get("page", 1)
        chunk.metadata["chunk_id"] = f"{source}_p{page}_c{idx+1}"

    print(f"[INFO] Split {len(documents)} document pages into {len(chunks)} text chunks.")
    return chunks
