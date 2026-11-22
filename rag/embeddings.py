"""
rag/embeddings.py
-----------------
Initializes and caches the local HuggingFace sentence-transformers embedding model.
Uses sentence-transformers/all-MiniLM-L6-v2 (384-dimensional dense vectors)
which runs completely locally without external API dependencies or costs.
"""

import os
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_huggingface import HuggingFaceEmbeddings

# Offline mode is opt-in. It is useful for air-gapped demos, but forcing it by
# default prevents the model from ever being downloaded on a fresh machine.
_OFFLINE = os.getenv("NUTRITION_OFFLINE", "").strip().lower() in {"1", "true", "yes", "on"}
if _OFFLINE:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Module-level singleton cache
_EMBEDDING_INSTANCE: Optional[Embeddings] = None


def get_embedding_model(
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    device: str = "cpu",
) -> Embeddings:
    """Return the cached local HuggingFace embedding model instance."""
    global _EMBEDDING_INSTANCE
    if _EMBEDDING_INSTANCE is None:
        print(f"[INFO] Initializing local embedding model: {model_name} on {device}...")
        _EMBEDDING_INSTANCE = HuggingFaceEmbeddings(
            model_name=model_name,
            model_kwargs={"device": device},
            encode_kwargs={"normalize_embeddings": True},
        )
        print("[INFO] Embedding model initialized successfully.")
    return _EMBEDDING_INSTANCE
