# rag/__init__.py
"""
RAG (Retrieval-Augmented Generation) package for nutrition knowledge base.
Provides document loading, chunking, local embeddings, persistent FAISS storage,
and nutrition retrieval tools.
"""
import os
# Windows stability flags: disable tqdm monitor thread and tokenizer parallelism
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
try:
    import tqdm
    tqdm.tqdm.monitor_interval = 0
except Exception:
    pass

from rag.document_loader import load_nutrition_documents
from rag.text_splitter import split_nutrition_documents
from rag.embeddings import get_embedding_model
from rag.vector_store import get_or_create_vector_store, build_vector_store, load_vector_store
from rag.retriever import get_retriever, retrieve_nutrition_knowledge

__all__ = [
    "load_nutrition_documents",
    "split_nutrition_documents",
    "get_embedding_model",
    "get_or_create_vector_store",
    "build_vector_store",
    "load_vector_store",
    "get_retriever",
    "retrieve_nutrition_knowledge",
]
