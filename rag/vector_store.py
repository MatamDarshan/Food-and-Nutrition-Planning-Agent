"""
rag/vector_store.py
-------------------
Manages local FAISS vector database persistence.
Enables fast, zero-rebuild startup by saving the FAISS index and metadata to disk.
"""

import sys
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS

from rag.document_loader import load_nutrition_documents
from rag.embeddings import get_embedding_model
from rag.text_splitter import split_nutrition_documents

DEFAULT_INDEX_DIR = BASE_DIR / "knowledge_base" / "faiss_index"


def is_index_persisted(index_dir: Path) -> bool:
    """Check if a valid FAISS index files exist in the target directory."""
    faiss_file = index_dir / "index.faiss"
    pkl_file = index_dir / "index.pkl"
    return faiss_file.exists() and pkl_file.exists()


def build_vector_store(
    chunks: list[Document],
    index_dir: Optional[Path] = None,
    embeddings: Optional[Embeddings] = None,
) -> FAISS:
    """Build a FAISS vector store from document chunks and persist it to disk."""
    if index_dir is None:
        index_dir = DEFAULT_INDEX_DIR
    if embeddings is None:
        embeddings = get_embedding_model()

    if not chunks:
        raise ValueError("Cannot build vector store from empty document chunks.")

    index_dir.mkdir(parents=True, exist_ok=True)
    print(f"[INFO] Indexing {len(chunks)} chunks into FAISS...")
    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(str(index_dir))
    print(f"[INFO] FAISS vector store persisted successfully to {index_dir}")
    return vector_store


def load_vector_store(
    index_dir: Optional[Path] = None,
    embeddings: Optional[Embeddings] = None,
) -> Optional[FAISS]:
    """Load a persistent FAISS index from disk."""
    if index_dir is None:
        index_dir = DEFAULT_INDEX_DIR
    if embeddings is None:
        embeddings = get_embedding_model()

    if not is_index_persisted(index_dir):
        return None

    try:
        print(f"[INFO] Loading persistent FAISS vector store from {index_dir}...")
        vector_store = FAISS.load_local(
            folder_path=str(index_dir),
            embeddings=embeddings,
            allow_dangerous_deserialization=True,
        )
        print("[INFO] FAISS vector store loaded successfully.")
        return vector_store
    except Exception as exc:
        print(f"[WARN] Failed to load persistent FAISS index: {exc}")
        return None


def get_or_create_vector_store(
    docs_dir: Optional[Path] = None,
    index_dir: Optional[Path] = None,
    embeddings: Optional[Embeddings] = None,
    force_rebuild: bool = False,
) -> FAISS:
    """Return the vector store, loading from disk if available or creating from documents."""
    if index_dir is None:
        index_dir = DEFAULT_INDEX_DIR
    if embeddings is None:
        embeddings = get_embedding_model()

    if not force_rebuild and is_index_persisted(index_dir):
        store = load_vector_store(index_dir=index_dir, embeddings=embeddings)
        if store is not None:
            return store

    # Build from documents
    print("[INFO] Building new FAISS vector store from nutrition documents...")
    docs = load_nutrition_documents(docs_dir=docs_dir)
    if not docs:
        raise RuntimeError("No nutrition documents available to build vector store.")

    chunks = split_nutrition_documents(docs)
    return build_vector_store(chunks=chunks, index_dir=index_dir, embeddings=embeddings)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build and persist the FAISS nutrition knowledge index.")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild index from documents even if index files exist on disk.",
    )
    args = parser.parse_args()

    print("[CLI] Initializing FAISS Vector Store Indexer...")
    vs = get_or_create_vector_store(force_rebuild=args.rebuild)
    print(f"[CLI] Index ready. Stored {vs.index.ntotal} vectors in FAISS index.")
