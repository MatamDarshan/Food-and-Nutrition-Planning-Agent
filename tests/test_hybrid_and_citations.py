"""
tests/test_hybrid_and_citations.py
----------------------------------
Hermetic tests for BM25, reciprocal-rank-fusion hybrid retrieval and the
deterministic citation verifier. All vector stores are in-memory fakes, so no
PDF parsing or embedding model is needed.
"""

import pytest
from langchain_core.documents import Document

from core.citations import format_verification, parse_citations, verify_citations
from rag.hybrid_retriever import retrieve_hybrid, retrieve_hybrid_nutrition_knowledge
from rag.sparse_index import BM25Index, tokenize


def _doc(chunk_id: str, source: str, page: int, text: str, condition=None) -> Document:
    metadata = {"chunk_id": chunk_id, "source": source, "page": page}
    if condition:
        metadata["condition"] = condition
    return Document(page_content=text, metadata=metadata)


CORE_DOCS = [
    _doc("c1", "icmr.pdf", 4, "Iron RDA is 19 mg/day for adult men and 29 mg/day for women."),
    _doc("c2", "icmr.pdf", 5, "Carbohydrates should provide 50 to 55 percent of daily energy."),
]
CONDITION_DOCS = [
    _doc("p1", "pcos.pdf", 2, "PCOS management focuses on insulin resistance and low GI foods.", "pcos"),
    _doc("p2", "thyroid.pdf", 1, "Thyroid health depends on adequate iodine and selenium intake.", "thyroid"),
]


class FakeStore:
    """Deterministic stand-in for a loaded FAISS store."""

    def __init__(self, documents):
        self.documents = documents

    def similarity_search_with_score(self, query, k=4, filter=None, **kwargs):
        if "cricket" in query.lower():
            return [(self.documents[0], 2.0)]  # above the relevance cutoff

        matches = self.documents
        if filter and "condition" in filter:
            matches = [
                doc for doc in matches
                if doc.metadata.get("condition") == filter["condition"]
            ]
        return [(doc, 0.7 + idx * 0.1) for idx, doc in enumerate(matches[:k])]


class TestBM25:
    """Lexical scoring must favour documents containing the query terms."""

    def test_tokenize_strips_stopwords_and_stems(self):
        tokens = tokenize("What are the nutritional benefits of millets?")
        assert "nutritional" in tokens
        assert "millet" in tokens
        assert "the" not in tokens
        assert "are" not in tokens

    def test_exact_term_ranking(self):
        index = BM25Index(CORE_DOCS)
        results = index.search("carbohydrates percent energy", k=2)
        assert results
        assert results[0][0].metadata["chunk_id"] == "c2"
        assert results[0][1] > 0

    def test_no_query_returns_nothing(self):
        assert BM25Index(CORE_DOCS).search("") == []
        assert len(BM25Index([])) == 0


class TestHybridRetrieval:
    """Fusion must combine both modalities without letting lexical noise through."""

    @staticmethod
    def _patch_assets(monkeypatch):
        assets = {
            "core": (FakeStore(CORE_DOCS), BM25Index(CORE_DOCS)),
            "conditions": (FakeStore(CONDITION_DOCS), BM25Index(CONDITION_DOCS)),
        }
        monkeypatch.setattr("rag.hybrid_retriever._collection_assets", lambda name: assets[name])

    def test_hybrid_fuses_dense_and_sparse(self, monkeypatch):
        self._patch_assets(monkeypatch)
        results = retrieve_hybrid("Iron RDA 19 mg/day", k=2, collections=("core",))
        assert results
        assert results[0].chunk_id == "c1"
        assert results[0].dense_rank == 1
        assert results[0].bm25_rank is not None
        assert results[0].rrf_score > 0
        assert "[Source: icmr.pdf, Page 4" in results[0].citation()

    def test_bm25_only_mode(self, monkeypatch):
        self._patch_assets(monkeypatch)
        results = retrieve_hybrid("carbohydrates energy", k=2, mode="bm25", collections=("core",))
        assert results[0].chunk_id == "c2"
        assert results[0].dense_rank is None

    def test_dense_only_mode(self, monkeypatch):
        self._patch_assets(monkeypatch)
        results = retrieve_hybrid("iron", k=1, mode="dense", collections=("core",))
        assert results[0].chunk_id == "c1"
        assert results[0].bm25_rank is None

    def test_condition_filter_is_applied_to_both_modalities(self, monkeypatch):
        self._patch_assets(monkeypatch)
        results = retrieve_hybrid(
            "insulin resistance management", condition="PCOS", k=3, collections=("conditions",)
        )
        assert results
        assert {passage.condition for passage in results} == {"pcos"}
        assert all(passage.source == "pcos.pdf" for passage in results)

    def test_lexical_only_noise_is_rejected_by_default(self, monkeypatch):
        self._patch_assets(monkeypatch)
        assert retrieve_hybrid("cricket world cup", k=3) == []

    def test_lexical_only_noise_can_be_allowed_explicitly(self, monkeypatch):
        self._patch_assets(monkeypatch)
        results = retrieve_hybrid(
            "iron 19 mg cricket", k=3, require_dense_support=False, collections=("core",)
        )
        assert results
        assert all(passage.dense_rank is None for passage in results)

    def test_invalid_mode_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown retrieval mode"):
            retrieve_hybrid("iron", mode="magic")

    def test_hybrid_tool_reports_passing_citations(self, monkeypatch):
        self._patch_assets(monkeypatch)
        output = retrieve_hybrid_nutrition_knowledge.invoke({"query": "Iron RDA 19 mg/day"})
        assert "**Answer (hybrid retrieval)**" in output
        assert "[Source: icmr.pdf, Page 4" in output
        assert "**Citation check:** PASS" in output


class TestCitationVerification:
    """Verification must accept grounded answers and reject fabricated claims."""

    PASSAGE = {
        "source": "icmr.pdf",
        "page": 4,
        "text": "Iron RDA is 19 mg/day for adult men and 29 mg/day for women. "
                "Vitamin C enhances absorption 2- to 3-fold.",
    }

    def test_parse_citations_with_and_without_condition(self):
        citations = parse_citations(
            "[Source: icmr.pdf, Page 4] and "
            "[Source: pcos.pdf, Page 2, Condition: pcos, RRF: 0.03]"
        )
        assert len(citations) == 2
        assert citations[0].source == "icmr.pdf"
        assert citations[1].condition == "pcos"

    def test_grounded_answer_passes(self):
        answer = (
            "**Answer**\nThe iron RDA is 19 mg/day for adult men. "
            "Vitamin C enhances absorption 2- to 3-fold. [Source: icmr.pdf, Page 4]"
        )
        report = verify_citations(answer, [self.PASSAGE])
        assert report.verified
        assert report.citations_checked == 1
        assert "PASS" in format_verification(report)

    def test_fabricated_numbers_and_claims_fail(self):
        answer = (
            "**Answer**\nThe iron RDA is 500 mg/day for adult men. "
            "The WHO recommends 12 cups of tea daily. [Source: icmr.pdf, Page 4]"
        )
        report = verify_citations(answer, [self.PASSAGE])
        assert not report.verified
        assert any("12" in issue or "500" in issue for issue in report.issues)
        assert report.unsupported_claims

    def test_unknown_citation_and_missing_citation_fail(self):
        unknown = verify_citations(
            "Iron RDA is 19 mg/day. [Source: missing.pdf, Page 9]", [self.PASSAGE]
        )
        assert not unknown.verified
        assert any("unknown passage" in issue for issue in unknown.issues)

        uncited = verify_citations("Iron RDA is 19 mg/day.", [self.PASSAGE])
        assert not uncited.verified
        assert any("no source citations" in issue.lower() for issue in uncited.issues)

    def test_langchain_document_passages_are_supported(self):
        answer = "Iron RDA is 19 mg/day. [Source: icmr.pdf, Page 4]"
        doc = _doc("c1", "icmr.pdf", 4, self.PASSAGE["text"])
        assert verify_citations(answer, [doc]).verified
