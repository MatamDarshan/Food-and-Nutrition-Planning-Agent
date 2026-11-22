"""
tests/test_ingestion.py
-----------------------
Hermetic tests for the multi-collection ingestion pipeline and the additive
condition-specific retriever. No PDF parsing or embedding model is exercised:
loaders, vector stores and index persistence are all replaced with in-memory
fakes so this module runs in milliseconds.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from rag import condition_retriever, ingest as ingest_module
from rag.document_loader import load_single_pdf
from rag.document_sources import CONDITION_SOURCES, metadata_for, normalise_condition, known_conditions
from rag.ingest import index_dir_for, summarise_documents


CONDITION_DOCS_DIR = (
    Path(__file__).resolve().parent.parent / "knowledge_base" / "condition_documents"
)


def _doc(source: str, page: int = 1, chunk_id: str = "c1", condition: str = "pcos") -> Document:
    return Document(
        page_content="PCOS nutrition guidance: low glycaemic carbohydrates and adequate protein.",
        metadata={
            "source": source,
            "page": page,
            "chunk_id": chunk_id,
            "condition": condition,
        },
    )


class _FakeLoader:
    """Minimal PyPDFLoader stand-in used to verify metadata normalization."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> list[Document]:
        return [
            Document(page_content="PCOS}_{\n guideline text", metadata={"page": 0}),
        ]


class TestDocumentManifest:
    """The manifest must describe every bundled condition document."""

    def test_every_bundled_condition_pdf_is_declared(self):
        bundled = {p.name for p in CONDITION_DOCS_DIR.glob("*.pdf")}
        assert bundled, "Condition PDFs are missing from knowledge_base/condition_documents/"
        assert bundled == set(CONDITION_SOURCES), "Manifest and bundled condition PDFs disagree"

    def test_manifest_metadata_is_additive_and_protected_fields_win(self, tmp_path, monkeypatch):
        monkeypatch.setattr("rag.document_loader.PyPDFLoader", _FakeLoader)
        pdf = tmp_path / "PCOS-Guideline-Summary-2023.pdf"
        pdf.write_bytes(b"%PDF fake")

        docs = load_single_pdf(
            pdf,
            extra_metadata={**metadata_for(pdf), "source": "HACK", "page": 99},
        )
        assert len(docs) == 1
        meta = docs[0].metadata
        assert meta["condition"] == "pcos"
        assert meta["collection"] == "conditions"
        assert meta["source"] == pdf.name
        assert meta["page"] == 1
        assert "HACK" not in meta.values()

    def test_condition_alias_normalization(self):
        assert normalise_condition("PCOS") == "pcos"
        assert normalise_condition("High Blood Pressure") == "hypertension"
        assert normalise_condition("lactose") == "lactose_intolerance"
        assert normalise_condition("  Thyroid  ") == "thyroid"
        assert "pcos" in known_conditions()


class TestIngestionPipeline:
    """Ingestion reports must be structured, dry-runnable and rebuild-safe."""

    def test_summarise_documents_groups_by_source_and_condition(self):
        summary = summarise_documents(
            [_doc("a.pdf", condition="pcos"), _doc("a.pdf", chunk_id="c2", condition="pcos")]
        )
        assert summary["chunks"] == 2
        assert summary["sources"] == 1
        assert summary["by_source"]["a.pdf"] == 2
        assert summary["by_condition"]["pcos"] == 2

    def test_dry_run_does_not_touch_disk(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            ingest_module, "load_collection", lambda collection: [_doc("a.pdf")]
        )
        target = tmp_path / "index"
        report = ingest_module.ingest(collection="conditions", index_dir=target, dry_run=True)

        assert report["status"] == "dry_run"
        assert report["pages"] == 1
        assert report["chunks"] == 1
        assert report["vectors"] == 0
        assert not target.exists()

    def test_build_persists_to_requested_directory(self, tmp_path, monkeypatch):
        captured = {}

        def fake_build(chunks, index_dir, embeddings=None):
            captured["chunks"] = chunks
            captured["index_dir"] = index_dir
            return SimpleNamespace(index=SimpleNamespace(ntotal=len(chunks)))

        monkeypatch.setattr(ingest_module, "load_collection", lambda collection: [_doc("a.pdf")])
        monkeypatch.setattr(ingest_module, "is_index_persisted", lambda target: False)
        monkeypatch.setattr(ingest_module, "build_vector_store", fake_build)

        target = tmp_path / "index"
        report = ingest_module.ingest(collection="conditions", index_dir=target)

        assert report["status"] == "built"
        assert report["vectors"] == 1
        assert captured["index_dir"] == target

    def test_existing_index_is_skipped_unless_forced(self, tmp_path, monkeypatch):
        calls = []

        def fake_build(chunks, index_dir, embeddings=None):
            calls.append(index_dir)
            return SimpleNamespace(index=SimpleNamespace(ntotal=len(chunks)))

        monkeypatch.setattr(ingest_module, "load_collection", lambda collection: [_doc("a.pdf")])
        monkeypatch.setattr(ingest_module, "is_index_persisted", lambda target: True)
        monkeypatch.setattr(ingest_module, "build_vector_store", fake_build)

        report = ingest_module.ingest(collection="conditions", index_dir=tmp_path / "index")
        assert report["status"] == "skipped"
        assert not calls

        forced = ingest_module.ingest(
            collection="conditions", index_dir=tmp_path / "index", force=True
        )
        assert forced["status"] == "built"
        assert len(calls) == 1

    def test_unknown_collection_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown collection"):
            ingest_module.ingest(collection="bogus")

    def test_index_dir_defaults_are_distinct(self):
        assert index_dir_for("core") != index_dir_for("conditions")


class TestConditionRetriever:
    """Condition retrieval must stay filtered, deduplicated and cited."""

    def test_missing_index_returns_empty_result(self, monkeypatch):
        monkeypatch.setattr(condition_retriever, "get_condition_store", lambda index_dir=None: None)
        assert condition_retriever.retrieve_condition_guidance("PCOS diet") == []
        assert condition_retriever.format_condition_guidance([]).startswith(
            "No relevant condition-specific guidance"
        )

    def test_distance_filter_dedup_and_metadata_filter(self, monkeypatch):
        captured = {}

        class FakeStore:
            def similarity_search_with_score(self, query, **kwargs):
                captured.update(kwargs)
                return [
                    (_doc("pcos.pdf", chunk_id="c1"), 0.40),
                    (_doc("pcos.pdf", chunk_id="c1"), 0.45),  # duplicate
                    (_doc("pcos.pdf", chunk_id="c2", page=2), 1.80),  # too far
                    (_doc("pcos.pdf", chunk_id="c3", page=3), 0.70),
                ]

        monkeypatch.setattr(
            condition_retriever, "get_condition_store", lambda index_dir=None: FakeStore()
        )
        results = condition_retriever.retrieve_condition_guidance(
            "PCOS diet plan", condition="PCOS", k=3
        )

        assert captured["filter"] == {"condition": "pcos"}
        assert [item["page"] for item in results] == [1, 3]
        assert all(item["is_relevant"] for item in results)
        assert all(item["distance"] <= condition_retriever.MAX_CONDITION_DISTANCE for item in results)

        formatted = condition_retriever.format_condition_guidance(results)
        assert "[Source: pcos.pdf, Page 1" in formatted
        assert "Vector Distance" in formatted

    def test_no_condition_name_skips_metadata_filter(self, monkeypatch):
        captured = {}

        class FakeStore:
            def similarity_search_with_score(self, query, **kwargs):
                captured.update(kwargs)
                return [(_doc("pcos.pdf"), 0.2)]

        monkeypatch.setattr(
            condition_retriever, "get_condition_store", lambda index_dir=None: FakeStore()
        )
        condition_retriever.retrieve_condition_guidance("healthy sleep habits")
        assert "filter" not in captured
