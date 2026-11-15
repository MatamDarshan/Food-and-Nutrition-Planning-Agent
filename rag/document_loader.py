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


def load_single_pdf(file_path: Path) -> list[Document]:
    """Load a single PDF document and attach normalized source/page metadata."""
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
            cleaned_docs.append(Document(page_content=clean_text, metadata=metadata))

        return cleaned_docs
    except Exception as exc:
        print(f"[WARN] Failed to load PDF {file_path.name}: {exc}")
        return []


def load_nutrition_documents(docs_dir: Optional[Path] = None) -> list[Document]:
    """Load all PDF documents from the knowledge_base/nutrition_documents/ directory."""
    if docs_dir is None:
        docs_dir = Path(__file__).resolve().parent.parent / "knowledge_base" / "nutrition_documents"

    if not docs_dir.exists():
        print(f"[WARN] Nutrition documents directory not found: {docs_dir}")
        return []

    pdf_files = sorted(list(docs_dir.glob("*.pdf")))
    if not pdf_files:
        print(f"[WARN] No PDF files found in {docs_dir}")
        return []

    all_docs: list[Document] = []
    for pdf_file in pdf_files:
        docs = load_single_pdf(pdf_file)
        all_docs.extend(docs)

    print(f"[INFO] Loaded {len(all_docs)} pages across {len(pdf_files)} PDF(s) from {docs_dir.name}")
    return all_docs
