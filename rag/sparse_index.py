"""
rag/sparse_index.py
-------------------
Dependency-free Okapi BM25 over the same document chunks used by FAISS.

Dense retrieval alone misses exact terms such as RDA values, food names and
condition labels. This module provides the lexical half of hybrid retrieval.
It is intentionally small and deterministic so tests can verify scores without
installing an extra package or downloading a model.
"""

import math
import re
from collections import Counter
from typing import Iterable

from langchain_core.documents import Document

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")

_STOPWORDS = frozenset(
    """
    a about above after again against all also am an and any are as at be because
    been before being below between both but by can could did do does doing down
    during each few for from further had has have having he her here hers herself
    him himself his how i if in into is it its itself just me more most my myself
    no nor not now of off on once only or other our ours ourselves out over own
    same she should so some such than that the their theirs them themselves then
    there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your yours
    yourself yourselves according diet dietary food foods eat eating help may use
    used using etc per indian india diets
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Lowercase, strip stopwords and apply a deliberately light stemmer."""
    tokens: list[str] = []
    for raw in _TOKEN_RE.findall(str(text or "").lower()):
        if len(raw) <= 2 or raw in _STOPWORDS:
            continue
        token = raw
        if len(token) > 5 and token.endswith("ies"):
            token = token[:-3] + "y"
        elif len(token) > 5 and token.endswith("ing"):
            token = token[:-3]
        elif len(token) > 4 and token.endswith("ed"):
            token = token[:-2]
        elif len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            token = token[:-1]
        if token and token not in _STOPWORDS:
            tokens.append(token)
    return tokens


class BM25Index:
    """In-memory Okapi BM25 index over a fixed document corpus."""

    def __init__(self, documents: Iterable[Document], k1: float = 1.5, b: float = 0.75):
        self.documents = list(documents)
        self.k1 = k1
        self.b = b
        self._term_freqs: list[Counter] = []
        self._doc_lengths: list[int] = []
        self._doc_freqs: Counter = Counter()

        for doc in self.documents:
            tokens = tokenize(doc.page_content)
            counts = Counter(tokens)
            self._term_freqs.append(counts)
            self._doc_lengths.append(len(tokens))
            for term in counts:
                self._doc_freqs[term] += 1

        self._avgdl = (
            sum(self._doc_lengths) / len(self._doc_lengths) if self._doc_lengths else 0.0
        )
        self._n = len(self.documents)

    def __len__(self) -> int:
        return self._n

    def _idf(self, term: str) -> float:
        freq = self._doc_freqs.get(term, 0)
        if not freq:
            return 0.0
        # Robertson/Sparck Jones IDF with +0.5 smoothing, floored at a small
        # positive value so a term present in every document still counts.
        return math.log(1.0 + (self._n - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, k: int = 10) -> list[tuple[Document, float]]:
        """Return up to ``k`` documents with a positive BM25 score."""
        if not self._n or not query or not str(query).strip():
            return []

        query_terms = Counter(tokenize(query))
        scores: list[float] = [0.0] * self._n
        for term, query_count in query_terms.items():
            idf = self._idf(term)
            if idf <= 0:
                continue
            for idx, term_freq in enumerate(self._term_freqs):
                freq = term_freq.get(term, 0)
                if not freq:
                    continue
                length_norm = 1.0 - self.b + self.b * (
                    self._doc_lengths[idx] / self._avgdl if self._avgdl else 1.0
                )
                denominator = freq + self.k1 * length_norm
                scores[idx] += query_count * idf * (freq * (self.k1 + 1.0)) / denominator

        ranked = sorted(
            (
                (score, idx)
                for idx, score in enumerate(scores)
                if score > 0.0
            ),
            key=lambda pair: (-pair[0], pair[1]),
        )
        return [(self.documents[idx], score) for score, idx in ranked[:k]]

    def search_with_rank(self, query: str, k: int = 10) -> list[tuple[Document, float, int]]:
        """Like :meth:`search` but includes the 1-based rank for fusion."""
        return [
            (doc, score, rank)
            for rank, (doc, score) in enumerate(self.search(query, k), start=1)
        ]
