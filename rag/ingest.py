"""
rag/ingest.py
-------------
Single entry point for rebuilding the nutrition knowledge indexes.

Two collections are indexed separately on purpose:

``core``
    The ICMR-NIN dietary guidelines. This is the index used by the existing
    chat tool and by the 16-query RAG benchmark, so it is never silently
    overwritten when condition documents change.

``conditions``
    Condition-specific reference documents (PCOS, thyroid, hypertension,
    lactose intolerance, obesity and sleep), each tagged with the canonical
    condition from :mod:`rag.document_sources`.

``all``
    Both collections in one index, useful for experiments and hybrid-retrieval
    development.

Examples
--------
    python -m rag.ingest --collection conditions --dry-run
    python -m rag.ingest --collection conditions --rebuild
    python -m rag.ingest --collection all --index-dir ./tmp_index --rebuild
"""

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from langchain_core.documents import Document

from rag.document_loader import (
    load_all_knowledge_documents,
    load_condition_documents,
    load_nutrition_documents,
)
from rag.text_splitter import split_nutrition_documents
from rag.vector_store import DEFAULT_INDEX_DIR, build_vector_store, is_index_persisted

DEFAULT_CONDITION_INDEX_DIR = BASE_DIR / "knowledge_base" / "condition_faiss_index"
VALID_COLLECTIONS = ("core", "conditions", "all")


def index_dir_for(collection: str, override: Optional[Path] = None) -> Path:
    """Resolve the destination index directory for a collection."""
    if override is not None:
        return Path(override)
    if collection == "conditions":
        return DEFAULT_CONDITION_INDEX_DIR
    return DEFAULT_INDEX_DIR


def load_collection(
    collection: str,
    core_docs_dir: Optional[Path] = None,
    condition_docs_dir: Optional[Path] = None,
) -> list[Document]:
    """Load the PDF pages belonging to a named collection."""
    if collection == "core":
        return load_nutrition_documents(core_docs_dir)
    if collection == "conditions":
        return load_condition_documents(condition_docs_dir)
    if collection == "all":
        return load_all_knowledge_documents(core_docs_dir, condition_docs_dir)
    raise ValueError(
        f"Unknown collection {collection!r}. Expected one of {', '.join(VALID_COLLECTIONS)}."
    )


def summarise_documents(documents: list[Document]) -> dict:
    """Summarise document counts by source and health condition."""
    by_source = Counter(doc.metadata.get("source", "unknown") for doc in documents)
    by_condition = Counter(
        doc.metadata.get("condition", "general") for doc in documents
    )
    return {
        "chunks": len(documents),
        "sources": len(by_source),
        "by_source": dict(sorted(by_source.items())),
        "by_condition": dict(sorted(by_condition.items())),
    }


def ingest(
    collection: str = "all",
    index_dir: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> dict:
    """Load, chunk and (optionally) persist a knowledge collection.

    Returns a structured report so the CLI, tests and future UI code can all
    consume the same result. No network access is required: embeddings run
    locally through :mod:`rag.embeddings`.
    """
    if collection not in VALID_COLLECTIONS:
        raise ValueError(
            f"Unknown collection {collection!r}. Expected one of {', '.join(VALID_COLLECTIONS)}."
        )

    target = index_dir_for(collection, index_dir)
    documents = load_collection(collection)
    if not documents:
        raise RuntimeError(
            f"No PDF pages found for collection {collection!r}. "
            "Check the knowledge_base directories before rebuilding."
        )

    split_kwargs = {}
    if chunk_size is not None:
        split_kwargs["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        split_kwargs["chunk_overlap"] = chunk_overlap
    chunks = split_nutrition_documents(documents, **split_kwargs)
    if not chunks:
        raise RuntimeError("Document splitting produced no chunks; refusing to build an empty index.")

    report = {
        "collection": collection,
        "index_dir": str(target),
        "pages": len(documents),
        "status": "dry_run" if dry_run else "built",
        "vectors": 0,
        **summarise_documents(chunks),
    }

    if dry_run:
        return report

    if is_index_persisted(target) and not force:
        report["status"] = "skipped"
        return report

    vector_store = build_vector_store(chunks=chunks, index_dir=target)
    report["vectors"] = int(vector_store.index.ntotal)
    return report


def _print_report(report: dict) -> None:
    """Render an ingestion report to stdout."""
    print(f"[INGEST] Collection : {report['collection']}")
    print(f"[INGEST] Destination: {report['index_dir']}")
    print(f"[INGEST] Pages      : {report['pages']}")
    print(f"[INGEST] Chunks     : {report['chunks']}")
    print(f"[INGEST] Status     : {report['status']}")
    print(f"[INGEST] Vectors    : {report['vectors']}")
    print("[INGEST] By source:")
    for source, count in report["by_source"].items():
        print(f"           - {source}: {count}")
    print("[INGEST] By condition:")
    for condition, count in report["by_condition"].items():
        print(f"           - {condition}: {count}")


def main(argv: Optional[list[str]] = None) -> int:
    """Command-line interface for ``python -m rag.ingest``."""
    parser = argparse.ArgumentParser(
        description="Rebuild the local FAISS nutrition knowledge indexes from bundled PDFs."
    )
    parser.add_argument(
        "--collection",
        choices=VALID_COLLECTIONS,
        default="conditions",
        help="Which document collection to index (default: conditions).",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=None,
        help="Override the destination directory (defaults to the collection's shipped index).",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Replace an existing index instead of skipping it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and chunk documents, print the manifest summary, but do not build embeddings.",
    )
    parser.add_argument("--chunk-size", type=int, default=None)
    parser.add_argument("--chunk-overlap", type=int, default=None)
    args = parser.parse_args(argv)

    report = ingest(
        collection=args.collection,
        index_dir=args.index_dir,
        dry_run=args.dry_run,
        force=args.rebuild,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    _print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
