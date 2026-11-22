"""
rag/document_loader.py
----------------------
Loads trusted nutrition PDF documents using LangChain PyPDFLoader.
Extracts page content and normalizes metadata for source attribution.
"""

from pathlib import Path
from typing import Optional
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader

from rag.document_sources import metadata_for

DEFAULT_DOCS_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "nutrition_documents"
DEFAULT_CONDITION_DOCS_DIR = (
    Path(__file__).resolve().parent.parent / "knowledge_base" / "condition_documents"
)

# These fields are derived from the PDF itself and must never be overwritten by
# manifest metadata, otherwise citations would point at the wrong document.
_PROTECTED_METADATA = frozenset({"source", "file_path", "page"})


def load_single_pdf(
    file_path: Path,
    extra_metadata: Optional[dict] = None,
) -> list[Document]:
    """Load a single PDF document and attach normalized source/page metadata.

    ``extra_metadata`` is merged in for manifest-derived fields such as the
    health condition tag; citation-critical fields are protected.
    """
    if not file_path.exists() or file_path.suffix.lower() != ".pdf":
        return []

    try:
        loader = PyPDFLoader(str(file_path))
        raw_docs = loader.load()
        cleaned_docs = []

        for doc in raw_docs:
            page_num = doc.metadata.get("page", 0) + 1  # 1-indexed for human readability
            clean_text = " ".join(doc.page_content.split())
            if not clean_text:
                continue

            metadata = {
                "source": file_path.name,
                "file_path": str(file_path),
                "page": page_num,
                "title": file_path.stem.replace("_", " "),
            }
            for key, value in (extra_metadata or {}).items():
                if key not in _PROTECTED_METADATA:
                    metadata[key] = value
            cleaned_docs.append(Document(page_content=clean_text, metadata=metadata))

        return cleaned_docs
    except Exception as exc:
        print(f"[WARN] Failed to load PDF {file_path.name}: {exc}")
        return []


def load_nutrition_documents(docs_dir: Optional[Path] = None) -> list[Document]:
    """Load the core ICMR-NIN documents from knowledge_base/nutrition_documents/.

    This intentionally does *not* include the condition collection: the core
    index is kept stable so existing retrieval benchmarks and tests remain
    comparable.  Use :func:`load_all_knowledge_documents` to include conditions.
    """
    if docs_dir is None:
        docs_dir = DEFAULT_DOCS_DIR

    if not docs_dir.exists():
        print(f"[WARN] Nutrition documents directory not found: {docs_dir}")
        return []

    pdf_files = sorted(list(docs_dir.glob("*.pdf")))
    if not pdf_files:
        print(f"[WARN] No PDF files found in {docs_dir}")
        return []

    all_docs: list[Document] = []
    for pdf_file in pdf_files:
        docs = load_single_pdf(pdf_file, extra_metadata=metadata_for(pdf_file))
        all_docs.extend(docs)

    print(f"[INFO] Loaded {len(all_docs)} pages across {len(pdf_files)} PDF(s) from {docs_dir.name}")
    return all_docs


def load_condition_documents(docs_dir: Optional[Path] = None) -> list[Document]:
    """Load the condition-specific reference PDFs with manifest metadata attached."""
    if docs_dir is None:
        docs_dir = DEFAULT_CONDITION_DOCS_DIR

    if not docs_dir.exists():
        print(f"[WARN] Condition documents directory not found: {docs_dir}")
        return []

    pdf_files = sorted(list(docs_dir.glob("*.pdf")))
    if not pdf_files:
        print(f"[WARN] No PDF files found in {docs_dir}")
        return []

    all_docs: list[Document] = []
    for pdf_file in pdf_files:
        docs = load_single_pdf(pdf_file, extra_metadata=metadata_for(pdf_file))
        all_docs.extend(docs)

    print(f"[INFO] Loaded {len(all_docs)} pages across {len(pdf_files)} condition PDF(s)")
    return all_docs


def load_all_knowledge_documents(
    docs_dir: Optional[Path] = None,
    condition_docs_dir: Optional[Path] = None,
) -> list[Document]:
    """Load both the core ICMR-NIN documents and the condition collection."""
    return load_nutrition_documents(docs_dir) + load_condition_documents(condition_docs_dir)
