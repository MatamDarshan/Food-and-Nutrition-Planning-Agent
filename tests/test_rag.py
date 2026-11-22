"""
tests/test_rag.py
-----------------
Comprehensive unit and integration tests for the Retrieval-Augmented Generation (RAG) system:
1. PDF Document Loading (PyPDFLoader)
2. Document Chunking (RecursiveCharacterTextSplitter)
3. Embedding Generation (HuggingFace sentence-transformers/all-MiniLM-L6-v2)
4. FAISS Vector Store Persistence & Loading
5. Relevant & Irrelevant Query Retrieval
6. Citation & Source Attribution Verification
7. LangGraph Chat Integration & Offline RAG Fallback
"""

import pytest
from langchain_core.messages import HumanMessage

from agent.graph import ALL_TOOLS, app_graph
from rag.document_loader import load_nutrition_documents
from rag.embeddings import get_embedding_model
from rag.retriever import (
    MAX_RELEVANCE_DISTANCE,
    format_retrieved_docs,
    get_retriever,
    retrieve_nutrition_knowledge,
    retrieve_relevant_chunks,
    retrieve_relevant_documents,
    retrieve_with_details,
)
from rag.text_splitter import split_nutrition_documents
from rag.vector_store import (
    get_or_create_vector_store,
    is_index_persisted,
    load_vector_store,
    DEFAULT_INDEX_DIR,
)


class TestRAGPipeline:
    """Test individual components of the RAG pipeline."""

    def test_pdf_loading(self):
        """Verify that PyPDFLoader reads the ICMR-NIN document with page metadata."""
        docs = load_nutrition_documents()
        assert len(docs) >= 1, "Should load at least 1 document page."
        for doc in docs:
            assert len(doc.page_content.strip()) > 50, "Document page should contain text."
            assert "source" in doc.metadata, "Metadata must include source document name."
            assert "page" in doc.metadata, "Metadata must include page number."
            assert doc.metadata["page"] >= 1, "Page number should be 1-indexed."

    def test_document_chunking(self):
        """Verify that RecursiveCharacterTextSplitter produces well-formed chunks."""
        docs = load_nutrition_documents()
        chunks = split_nutrition_documents(docs)
        assert len(chunks) > len(docs), "Chunking should create multiple chunks per document."
        for idx, chunk in enumerate(chunks):
            assert "chunk_id" in chunk.metadata, f"Chunk {idx} missing chunk_id."
            assert "source" in chunk.metadata, f"Chunk {idx} missing source."
            assert "page" in chunk.metadata, f"Chunk {idx} missing page."
            assert len(chunk.page_content) > 0, f"Chunk {idx} is empty."

    def test_embedding_generation(self):
        """Verify that the local HuggingFace embedding model produces 384-dim vectors."""
        embeddings = get_embedding_model()
        vec = embeddings.embed_query("Nutritional benefits of ragi and millets")
        assert isinstance(vec, list), "Embedding should be a list of floats."
        assert len(vec) == 384, f"Expected 384-dimensional vector, got {len(vec)}."

    def test_faiss_persistence_and_loading(self):
        """Verify that FAISS index persists on disk and loads without rebuilding."""
        assert is_index_persisted(DEFAULT_INDEX_DIR), "FAISS index should be persisted on disk."
        vs = load_vector_store(index_dir=DEFAULT_INDEX_DIR)
        assert vs is not None, "Failed to load persisted FAISS vector store."
        # Ensure we can search the loaded index
        results = vs.similarity_search("protein", k=2)
        assert len(results) == 2, "Loaded FAISS index should return k nearest neighbors."


class TestRAGRetriever:
    """Test retrieval accuracy, citations, and irrelevant query handling."""

    def test_millets_query_retrieval(self):
        """Test retrieval for 'What are the nutritional benefits of millets?'."""
        query = "What are the nutritional benefits of millets?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant millet excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["millet", "ragi", "calcium", "glycemic"]), (
            "Retrieved excerpts should mention millets and nutrients."
        )

        # Test tool invocation
        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output, "Tool output must include source citation."
        assert "Page" in tool_output, "Tool output must include page citation."

    def test_protein_query_retrieval(self):
        """Test retrieval for 'Which Indian foods are good sources of protein?'."""
        query = "Which Indian foods are good sources of protein?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant protein excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["protein", "paneer", "dal", "amino acid", "pulse"]), (
            "Retrieved excerpts should mention Indian protein sources."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_dietary_fibre_query_retrieval(self):
        """Test retrieval for 'Explain the importance of dietary fibre.'."""
        query = "Explain the importance of dietary fibre."
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant dietary fiber excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["fibre", "fiber", "microbiome", "digestion", "soluble"]), (
            "Retrieved excerpts should explain dietary fibre."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_whole_grains_query_retrieval(self):
        """Test retrieval for 'What are the differences between whole grains and refined grains?'."""
        query = "What are the differences between whole grains and refined grains?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve whole grains vs refined grains excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["whole grain", "refined", "bran", "germ", "endosperm"]), (
            "Retrieved excerpts should describe whole grains and refined grains."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_calcium_query_retrieval(self):
        """Test retrieval for 'What are the top dietary sources of calcium in Indian diets?'."""
        query = "What are the top dietary sources of calcium in Indian diets?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant calcium excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["calcium", "ragi", "til", "sesame", "milk", "1,000"]), (
            "Retrieved excerpts should mention Indian calcium sources."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_iron_query_retrieval(self):
        """Test retrieval for 'What is the RDA for iron and how can absorption be enhanced?'."""
        query = "What is the RDA for iron and how can absorption be enhanced?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant iron excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["iron", "19", "29", "vitamin c", "bajra"]), (
            "Retrieved excerpts should mention iron guidelines."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_vitamin_b12_query_retrieval(self):
        """Test retrieval for 'Why is Vitamin B12 important and what are its sources?'."""
        query = "Why is Vitamin B12 important and what are its sources for Indian vegetarians?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant Vitamin B12 excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["b12", "cobalamin", "milk", "dairy", "vegan", "2.2"]), (
            "Retrieved excerpts should mention Vitamin B12."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_healthy_fats_query_retrieval(self):
        """Test retrieval for 'What are the ICMR-NIN recommendations for visible cooking oils?'."""
        query = "What are the ICMR-NIN recommendations for visible cooking oils and fatty acid balance?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant dietary fats excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["visible fat", "mufa", "pufa", "trans fat", "20g"]), (
            "Retrieved excerpts should mention cooking oils guidelines."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_carbohydrates_query_retrieval(self):
        """Test retrieval for 'What percentage of daily calories should come from carbohydrates?'."""
        query = "What percentage of daily calories should come from carbohydrates according to ICMR-NIN?"
        docs = retrieve_relevant_documents(query, k=3)
        assert len(docs) > 0, "Should retrieve relevant carbohydrate excerpts."
        content_joined = " ".join(d.page_content for d in docs).lower()
        assert any(w in content_joined for w in ["carbohydrate", "50%", "55%", "complex", "sugar"]), (
            "Retrieved excerpts should mention carbohydrate guidelines."
        )

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "[Source:" in tool_output
        assert "Page" in tool_output

    def test_multiple_irrelevant_queries(self):
        """Verify that out-of-domain queries across multiple domains are cleanly rejected."""
        irrelevant_queries = [
            "Who won the cricket world cup?",
            "What rocket launched Apollo 11 to the moon?",
            "How do you replace brake pads on a Toyota Camry?",
            "What is the capital city of Australia?",
            "How do you configure a reverse proxy in Nginx?",
        ]
        for q in irrelevant_queries:
            docs = retrieve_relevant_documents(q, k=3)
            assert len(docs) == 0, f"Query '{q}' should be rejected as irrelevant."
            tool_output = retrieve_nutrition_knowledge.invoke({"query": q})
            assert "No relevant nutrition document sections were found" in tool_output

    def test_retrieve_with_details_structure(self):
        """Verify that retrieve_with_details outputs structured dicts with exact L2 vector distance."""
        details = retrieve_with_details("benefits of millets", k=2)
        assert len(details) == 2
        for item in details:
            assert "document" in item
            assert "page" in item
            assert "distance" in item
            assert isinstance(item["distance"], float)
            assert "is_relevant" in item
            assert item["is_relevant"] is True
            assert "text" in item
            assert len(item["text"]) > 0

    def test_irrelevant_query_handling(self):
        """Verify that completely out-of-domain queries return the graceful notice."""
        query = "Who won the cricket world cup?"
        docs = retrieve_relevant_documents(query, k=3)
        # Should be filtered out by relevance distance threshold
        assert len(docs) == 0, "Irrelevant queries should not produce high-confidence document matches."

        tool_output = retrieve_nutrition_knowledge.invoke({"query": query})
        assert "No relevant nutrition document sections were found" in tool_output


class TestRAGAgentIntegration:
    """Test RAG tool registration and LangGraph chat integration."""

    def test_retrieval_tool_registered_in_all_tools(self):
        """Verify that retrieve_nutrition_knowledge is in the agent's tool roster."""
        tool_names = [getattr(t, "name", str(t)) for t in ALL_TOOLS]
        assert "retrieve_nutrition_knowledge" in tool_names, (
            f"Expected retrieve_nutrition_knowledge in ALL_TOOLS: {tool_names}"
        )

    def test_offline_chat_rag_fallback(self):
        """Verify that conversational questions retrieve and format RAG guidelines even offline."""
        input_state = {
            "messages": [
                HumanMessage(content="USER GOALS: Initial baseline."),
                HumanMessage(content="What are the nutritional benefits of millets?"),
            ],
            "user_profile": {"diet_type": "veg", "allergies": []},
            "nutrition_targets": {"calorie_target": 2000.0},
        }
        config = {"configurable": {"thread_id": "test_rag_offline_chat"}}
        result = app_graph.invoke(input_state, config=config)
        final_text = result.get("final_response", "")
        assert len(final_text) > 0, "Should produce a response."
        assert any(w in final_text.lower() for w in ["millet", "ragi", "guidelines", "icmr-nin"]), (
            "Offline chat turn should leverage RAG knowledge base for nutrition guidance."
        )


class TestRAGAnswerQuality:
    """Tests for the readable, cited answer layer added on top of retrieval."""

    @staticmethod
    def _answer_body(output: str) -> str:
        return output.split("**Supporting excerpts**")[0].strip()

    def test_answer_is_clean_and_structured(self):
        """The tool output must not leak PDF control characters or raw chunk dumps."""
        output = retrieve_nutrition_knowledge.invoke(
            {"query": "What are the nutritional benefits of millets like ragi and bajra?"}
        )
        assert "\x7f" not in output
        assert not any(ord(ch) < 32 and ch not in "\n\t" for ch in output), (
            "Retrieved output should not contain raw PDF control characters."
        )
        assert "**Answer" in output, "Output should contain a composed answer section."
        assert "**Supporting excerpts**" in output
        assert "**Sources**" in output
        assert "[Source:" in output and "Page" in output
        assert "Vector Distance" in output
        assert "millet" in output.lower()

    def test_answer_contains_the_asked_fact(self):
        """The composed answer should surface the specific value asked about."""
        iron_output = retrieve_nutrition_knowledge.invoke(
            {"query": "What is the RDA for iron and how can absorption be enhanced?"}
        )
        iron_answer = self._answer_body(iron_output)
        assert "19 mg" in iron_answer, f"Iron answer missed the RDA value: {iron_answer}"
        assert "vitamin c" in iron_answer.lower(), "Iron answer should mention absorption enhancers."

        calcium_output = retrieve_nutrition_knowledge.invoke(
            {"query": "What are the top dietary sources of calcium in Indian diets?"}
        )
        calcium_answer = self._answer_body(calcium_output)
        assert any(term in calcium_answer.lower() for term in ["ragi", "sesame", "344 mg"]), (
            f"Calcium answer missed Indian food sources: {calcium_answer}"
        )

    def test_mmr_retrieval_returns_distinct_chunks(self):
        """Diverse retrieval must not return the same chunk more than once."""
        chunks = retrieve_relevant_chunks(
            "What are the nutritional benefits of millets?",
            k=3,
            diverse=True,
        )
        chunk_ids = [doc.metadata.get("chunk_id") for doc, _ in chunks]
        assert len(chunk_ids) == len(set(chunk_ids)), "MMR retrieval returned duplicate chunks."
        assert all(score <= MAX_RELEVANCE_DISTANCE for _, score in chunks)

    def test_irrelevant_queries_are_still_rejected(self):
        """Answer composition must not weaken out-of-domain rejection."""
        for query in ["How do I mine bitcoin with a GPU?", "What is the capital of Australia?"]:
            output = retrieve_nutrition_knowledge.invoke({"query": query})
            assert output.startswith("No relevant nutrition document sections were found")
            assert "\x7f" not in output

