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
    format_retrieved_docs,
    get_retriever,
    retrieve_nutrition_knowledge,
    retrieve_relevant_documents,
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
