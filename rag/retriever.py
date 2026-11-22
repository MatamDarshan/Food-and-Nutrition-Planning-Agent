"""
rag/retriever.py
----------------
Retrieval interface and LangChain tool for querying the nutrition knowledge base.
Provides dense vector similarity search with document source attribution.
"""

import os
import math
import re
from typing import Any, Optional, Union
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.vectorstores import VectorStoreRetriever

from rag.vector_store import get_or_create_vector_store

_RETRIEVER_INSTANCE: Optional[VectorStoreRetriever] = None
_VECTOR_STORE: Optional[Any] = None

# Euclidean (L2) distance threshold for normalized 384-dimensional embeddings.
# For unit vectors, squared Euclidean distance d^2 = 2 * (1 - cosine_similarity).
# A threshold of 1.25 corresponds to cosine similarity >= 0.22.
# Distance values represent metric vector space distance and must not be interpreted as probabilities or percentages.
MAX_RELEVANCE_DISTANCE = 1.25

# Retrieval diversification: pull a wider candidate pool, then pick k chunks that
# are both close to the query and different from each other (MMR).
DEFAULT_FETCH_K = 12
DEFAULT_LAMBDA_MULT = 0.7
DEFAULT_ANSWER_K = 3

NO_MATCH_NOTICE = (
    "No relevant nutrition document sections were found in the ICMR-NIN knowledge base for this query. "
    "The knowledge base does not contain sufficient information on this specific topic."
)

# PDF extraction leaves control characters and soft hyphens behind. They are not
# meaningful content, so strip them before anything is shown to a user.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_INLINE_WHITESPACE = re.compile(r"[ \t\u00a0]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])")

_STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are as at be because been
    before being below between both but by can could did do does doing down during each
    few for from further had has have having he her here hers herself him himself his how
    i if in into is it its itself just me more most my myself no nor not now of off on once
    only or other our ours ourselves out over own same she should so some such than that the
    their theirs them themselves then there these they this those through to too under until
    up very was we were what when where which while who whom why will with would you your
    yours yourself yourselves according diet dietary food foods eat eating help may use used
    using etc per indian india diets
    """.split()
)

# Sentences with almost no function words are usually flattened table cells rather
# than prose, so they make poor answer sentences.
_FUNCTION_WORDS = frozenset(
    "a an the of to in on for and or but with by from as at is are was were be been "
    "that which this these those it its their there is can may should will".split()
)


def clean_excerpt_text(text: str) -> str:
    """Turn raw PDF text into readable prose.

    Removes control characters (``\\x7f`` bullets are converted to real bullets),
    repairs words split by line-end hyphenation, and joins PDF-wrapped lines while
    keeping bullets and headings as separate blocks.
    """
    if not text:
        return ""

    cleaned = str(text).replace("\u00ad", "").replace("\x7f", " • ")
    cleaned = _CONTROL_CHARS.sub(" ", cleaned)
    cleaned = cleaned.replace("\u00a0", " ")
    cleaned = cleaned.replace(" vs. ", " vs ")
    cleaned = cleaned.replace(" Vs. ", " vs ")
    # Re-join words hyphenated across a PDF line break: "nutri-\ntion" -> "nutrition".
    cleaned = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", cleaned)
    cleaned = re.sub(r"\s+•\s+", "\n• ", cleaned)
    cleaned = re.sub(r"•(?:\s*•)+", "•", cleaned)
    cleaned = re.sub(r"[ \t]*\n[ \t]*", "\n", cleaned)

    blocks: list[str] = []
    for raw_line in cleaned.split("\n"):
        line = _INLINE_WHITESPACE.sub(" ", raw_line).strip()
        if not line:
            continue
        is_new_block = (
            not blocks
            or line.startswith("•")
            or blocks[-1].startswith("•")
            or blocks[-1].endswith((".", ":", ";", "?", "!"))
            or line[0].isupper()
        )
        if is_new_block:
            blocks.append(line)
        else:
            blocks[-1] = f"{blocks[-1]} {line}"

    return "\n".join(blocks).strip()


def _query_terms(query: str) -> set[str]:
    """Content words used to score retrieved sentences against the question."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", query.lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _sentence_tokens(sentence: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", sentence.lower())
        if token not in _STOPWORDS
    }


def _clean_label(text: str) -> str:
    """Normalise a section label such as ``2. Iron:`` or ``. Key Millets:``."""
    label = text.rstrip(":").strip(" .•\n\t")
    label = re.sub(r"^\d+[.)]\s*", "", label)
    return label.strip()


def _split_sentences(block: str) -> list[str]:
    """Split cleaned text into sentence-like units, keeping short section labels.

    PDF bullet lists often put the subject on its own line (``2. Iron:``) and the
    value in the bullet below. Carrying the label onto the bullet keeps sentences
    such as "Iron: Recommended Dietary Allowance ... 19 mg/day" self-contained.
    """
    parts: list[str] = []
    label = ""
    for raw_line in block.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        stripped = line.lstrip("• ").strip()
        looks_like_label = (
            len(stripped) <= 70
            and stripped.endswith(":")
            and not stripped.lower().startswith(("http", "www"))
        )
        if looks_like_label:
            label = _clean_label(stripped)
            continue
        for piece in line.split("•"):
            piece = piece.strip(" \n\t-–—.")
            if not piece:
                continue
            for part in _SENTENCE_BOUNDARY.split(piece):
                sentence = part.strip().strip("•-–— \n\t")
                sentence = re.sub(r"^[.\s]+", "", sentence)
                is_numbered_heading = bool(re.match(r"^\d+[.)]\s+\S", sentence))
                if (
                    len(sentence) <= 70
                    and sentence.endswith(":")
                    and (is_numbered_heading or not label)
                ):
                    label = _clean_label(sentence)
                    continue
                if len(sentence) < 25:
                    continue
                if label and label.lower() not in sentence.lower():
                    sentence = f"{label}: {sentence}"
                parts.append(sentence)
    return parts


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def compose_extractive_answer(
    query: str,
    texts: list[str],
    max_sentences: int = 3,
    max_chars: int = 700,
) -> str:
    """Compose a readable answer from retrieved excerpts without an LLM.

    Sentences are scored by inverse-document-frequency weighted coverage of the
    question, near-duplicate sentences are dropped, and the survivors are returned
    in document order so the answer reads as a short extract rather than a raw
    chunk dump. Rare, specific words (``iron``, ``sources``) count more than words
    that appear everywhere in the retrieved passages (``rda``, ``chapter``).
    """
    terms = _query_terms(query)
    wants_numbers = bool(
        re.search(r"\b(percentage|percent|rda|allowance|how much|how many)\b", query.lower())
    )
    candidates: list[tuple[int, str]] = []
    for order, text in enumerate(texts):
        candidates.extend((order, sentence) for sentence in _split_sentences(text))

    if not candidates:
        fallback = " ".join(text.replace("\n", " ") for text in texts[:1]).strip()
        fallback = fallback.strip(" .•")
        if not fallback:
            return ""
        if len(fallback) > max_chars:
            fallback = fallback[:max_chars].rsplit(" ", 1)[0] + "…"
        return fallback

    # IDF over the candidate pool keeps generic wording from dominating the answer.
    document_frequency: dict[str, int] = dict.fromkeys(terms, 0)
    token_cache: list[set[str]] = []
    for _, sentence in candidates:
        tokens = _sentence_tokens(sentence)
        token_cache.append(tokens)
        for term in terms & tokens:
            document_frequency[term] += 1
    total = len(candidates)
    weights = {
        term: 1.0 + 0.5 * math.log((1 + total) / (1 + document_frequency[term]))
        for term in terms
    }
    weight_sum = sum(weights.values()) or 1.0
    wants_sources = "source" in query.lower() or "sources" in query.lower()

    scored: list[tuple[float, int, str]] = []
    for (order, sentence), tokens in zip(candidates, token_cache):
        if len(sentence) > 600:  # table rows and other low-value blobs
            continue
        if len(sentence) < 140 and re.search(r":\s*\d+\.?$", sentence):
            continue  # dangling list intro such as "Top Protein Sources: 1"
        raw_tokens = re.findall(r"[a-z0-9]+", sentence.lower())
        if (
            sum(1 for token in raw_tokens if token in _FUNCTION_WORDS) < 2
            and not re.search(r"\d", sentence)
        ):
            continue  # flattened table cell, not a sentence
        if sentence[0].islower():
            continue  # mid-table fragment rather than a sentence
        words = sentence.split()
        if len(words) > 14 and sum(1 for word in words if word[:1].isupper()) / len(words) > 0.55:
            continue  # document title or table header
        matched = terms & tokens
        coverage = sum(weights[term] for term in matched) / weight_sum
        density = sum(weights[term] for term in matched) / (len(tokens) ** 0.5)
        score = coverage + (0.25 * density)
        if wants_numbers and re.search(r"\d", sentence):
            score += 0.15
        if re.match(r"^(They|It|This|These|Those|Such)\b", sentence):
            continue  # pronoun-only lead with no antecedent in the answer
        if wants_sources and re.search(r"\bsources?\b", sentence, re.IGNORECASE):
            score += 0.25
        if score <= 0 and terms:
            continue
        # Earlier (better-ranked) chunks get a small tie-breaking boost.
        score += 0.02 * max(0, len(texts) - order)
        scored.append((score, order, sentence))

    if not scored:
        fallback = " ".join(text.replace("\n", " ") for text in texts[:1]).strip()
        fallback = fallback.strip(" .•")
        if not fallback:
            return ""
        if len(fallback) > max_chars:
            fallback = fallback[:max_chars].rsplit(" ", 1)[0] + "…"
        return fallback

    scored.sort(key=lambda item: (-item[0], item[1]))
    # Drop weak matches that only share generic words with the question.
    minimum_score = scored[0][0] * 0.45
    selected: list[tuple[int, str]] = []
    selected_signatures: list[set[str]] = []
    for score, order, sentence in scored:
        if selected and score < minimum_score:
            break
        signature = _sentence_tokens(sentence)
        if any(_jaccard(signature, other) > 0.72 for other in selected_signatures):
            continue
        selected.append((order, sentence))
        selected_signatures.append(signature)
        if len(selected) >= max_sentences:
            break

    selected.sort(key=lambda item: -item[0])
    seen_labels: set[str] = set()
    display_sentences: list[str] = []
    for _, sentence in selected:
        label_match = re.match(r"^([A-Z][^:]{2,60}):\s+", sentence)
        if label_match:
            label = label_match.group(1).strip().lower()
            remainder = sentence[label_match.end():]
            if label in seen_labels and len(remainder) > 60:
                sentence = remainder
            else:
                seen_labels.add(label)
        if sentence and sentence[-1] not in ".!?…":
            sentence += "."
        display_sentences.append(sentence)

    answer = " ".join(display_sentences).strip()
    # Remove leftovers from PDF line breaks such as " . " or a dangling list marker.
    answer = re.sub(r"^[ .•]+", "", answer)
    answer = re.sub(r"\s+\.\s+", ". ", answer)
    answer = re.sub(r"\s+\d+\.$", "", answer).strip()
    if answer and answer[-1] not in ".!?…":
        answer += "."
    if len(answer) > max_chars:
        answer = answer[:max_chars].rsplit(" ", 1)[0] + "…"
    return answer


def _get_vector_store() -> Any:
    """Return a process-wide FAISS store instead of reloading it per query."""
    global _VECTOR_STORE
    if _VECTOR_STORE is None:
        _VECTOR_STORE = get_or_create_vector_store()
    return _VECTOR_STORE


def get_retriever(k: int = 3) -> VectorStoreRetriever:
    """Return a cached VectorStoreRetriever instance configured for top-k retrieval."""
    global _RETRIEVER_INSTANCE
    if _RETRIEVER_INSTANCE is None:
        _RETRIEVER_INSTANCE = _get_vector_store().as_retriever(search_kwargs={"k": k})
    return _RETRIEVER_INSTANCE


def retrieve_relevant_chunks(
    query: str,
    k: int = 3,
    max_distance: float = MAX_RELEVANCE_DISTANCE,
    diverse: bool = False,
    fetch_k: int = DEFAULT_FETCH_K,
    lambda_mult: float = DEFAULT_LAMBDA_MULT,
) -> list[tuple[Document, float]]:
    """Retrieve top-k document chunks and their Euclidean vector distances, filtered by threshold.

    When ``diverse`` is True, a wider candidate pool is fetched and Maximal Marginal
    Relevance (MMR) selects chunks that are relevant *and* not near-duplicates of each
    other. This matters for dense PDFs where three neighbouring chunks often repeat
    the same paragraph.
    """
    store = _get_vector_store()
    if diverse:
        vector = store.embedding_function.embed_query(query)
        results = store.max_marginal_relevance_search_with_score_by_vector(
            vector,
            k=max(1, k),
            fetch_k=max(fetch_k, k),
            lambda_mult=lambda_mult,
        )
    else:
        results = store.similarity_search_with_score(query, k=max(1, k))
    return [(doc, float(score)) for doc, score in results if float(score) <= max_distance]


def retrieve_relevant_documents(
    query: str,
    k: int = 3,
    max_distance: float = MAX_RELEVANCE_DISTANCE,
) -> list[Document]:
    """Retrieve top-k documents matching the query, filtering out irrelevant chunks by distance threshold."""
    chunks_with_scores = retrieve_relevant_chunks(query=query, k=k, max_distance=max_distance)
    return [doc for doc, _ in chunks_with_scores]


def retrieve_with_details(
    query: str,
    k: int = 3,
    max_distance: float = MAX_RELEVANCE_DISTANCE,
) -> list[dict[str, Any]]:
    """Retrieve detailed metadata and vector distances for evaluation and inspection."""
    results = _get_vector_store().similarity_search_with_score(query, k=k)
    details = []
    for doc, score in results:
        dist = float(score)
        details.append({
            "document": doc.metadata.get("source", "ICMR-NIN Guidelines"),
            "page": doc.metadata.get("page", 1),
            "chunk_id": doc.metadata.get("chunk_id", ""),
            "distance": round(dist, 4),
            "is_relevant": dist <= max_distance,
            "text": clean_excerpt_text(doc.page_content),
        })
    return details


def _citation(doc: Document) -> str:
    source = os.path.basename(str(doc.metadata.get("source", "ICMR-NIN Guidelines"))) or "ICMR-NIN Guidelines"
    page = doc.metadata.get("page", 1)
    return f"[Source: {source}, Page {page}]"


def format_retrieved_docs(
    docs_or_tuples: Union[list[Document], list[tuple[Document, float]]],
    query: str = "",
) -> str:
    """Format retrieved chunks into a readable, cited answer.

    Instead of dumping raw excerpts with debug scores, this composes a short
    extractive answer from the retrieved sentences and keeps each source excerpt
    compact. Distance values stay available as a clearly-labelled retrieval metric;
    they are never described as probabilities or confidence percentages.
    """
    if not docs_or_tuples:
        return NO_MATCH_NOTICE

    docs: list[Document] = []
    distances: list[float] = []
    for item in docs_or_tuples:
        if isinstance(item, tuple):
            doc, dist = item
            docs.append(doc)
            distances.append(float(dist))
        else:
            docs.append(item)

    cleaned = [clean_excerpt_text(doc.page_content) for doc in docs]
    answer = compose_extractive_answer(query, cleaned)

    lines: list[str] = []
    if answer:
        lines.append("**Answer (from the ICMR-NIN knowledge base)**")
        lines.append(answer)
        lines.append("")

    lines.append("**Supporting excerpts**")
    for idx, (doc, text) in enumerate(zip(docs, cleaned), 1):
        snippet = re.sub(r"\s*\n\s*•?\s*", " ", text).strip(" .•")
        if len(snippet) > 320:
            snippet = snippet[:320].rsplit(" ", 1)[0] + "…"
        lines.append(f"{idx}. {snippet} {_citation(doc)}")

    # De-duplicate repeated pages while preserving retrieval order.
    sources: list[str] = []
    for doc in docs:
        citation = _citation(doc)
        if citation not in sources:
            sources.append(citation)
    if sources:
        lines.append("")
        lines.append("**Sources**")
        lines.extend(f"- {citation}" for citation in sources)

    if distances:
        score_text = ", ".join(f"{dist:.4f}" for dist in distances)
        lines.append("")
        lines.append(
            f"*Vector Distance (L2, lower is closer; not a confidence percentage): {score_text}*"
        )

    return "\n".join(lines).strip()


@tool
def retrieve_nutrition_knowledge(query: str) -> str:
    """Retrieve authoritative scientific nutrition knowledge and guidelines from ICMR-NIN documents.

    Use this tool to answer conceptual or educational dietary questions, such as:
    - Nutritional benefits and therapeutic properties of millets (ragi, bajra, jowar).
    - Top Indian sources of dietary protein and cereal-pulse amino acid synergy.
    - The biological importance, daily requirements, and types of dietary fiber.
    - Anatomical and nutritional differences between whole grains and refined grains.
    - Micronutrient requirements (Calcium, Iron, Vitamin B12) and bioavailability.
    - Healthy dietary fats, cooking oils balance (SFA/MUFA/PUFA), and trans fat elimination.
    - Carbohydrate quality, energy contribution (50-55%), and food synergies.

    Args:
        query: Specific nutritional query, e.g. 'benefits of millets' or 'sources of dietary fiber'.

    Returns:
        A short cited answer plus supporting excerpts with document names and page numbers.
        Returns a notice if the knowledge base does not contain sufficient information.
    """
    try:
        chunks_with_scores = retrieve_relevant_chunks(
            query=query,
            k=DEFAULT_ANSWER_K,
            diverse=True,
            fetch_k=DEFAULT_FETCH_K,
            lambda_mult=DEFAULT_LAMBDA_MULT,
        )
        return format_retrieved_docs(chunks_with_scores, query=query)
    except Exception as exc:
        return f"[ERROR] Failed to retrieve nutrition knowledge: {str(exc)}"
