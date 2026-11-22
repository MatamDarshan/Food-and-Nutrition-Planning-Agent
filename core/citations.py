"""
core/citations.py
-----------------
Deterministic citation verification for RAG answers.

This is deliberately rule-based, not LLM-based: it checks that every citation
points at a passage that was actually retrieved, that numeric claims appear in
the cited text, and that the wording of each substantive sentence overlaps the
cited evidence. It runs offline and is fast enough to execute on every answer.
"""

import re
from typing import Any, Iterable

from pydantic import BaseModel, Field

_CITATION_RE = re.compile(
    r"\[Source:\s*(?P<source>[^,\]]+?)\s*,\s*Page\s*(?P<page>\d+)"
    r"(?:\s*,\s*Condition:\s*(?P<condition>[^,\]]+?))?"
    r"(?:\s*,|\])",
    re.IGNORECASE,
)
_HEADER_RE = re.compile(r"^\s*\*{1,2}[^*]+\*{1,2}\s*$")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an the of to in on for and or but with by from as at is are was were be "
    "been being that this these those it its their there here can may should "
    "will would which what when where who how into about after before not no".split()
)


class Citation(BaseModel):
    """A parsed ``[Source: …, Page N]`` marker."""

    source: str
    page: int
    condition: str | None = None


class CitationReport(BaseModel):
    """Result of verifying an answer against the passages it cites."""

    verified: bool
    citations_checked: int = 0
    supported_claims: int = 0
    issues: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


def parse_citations(text: str) -> list[Citation]:
    """Extract all citation markers from a formatted answer."""
    citations: list[Citation] = []
    for match in _CITATION_RE.finditer(str(text or "")):
        citations.append(
            Citation(
                source=match.group("source").strip(),
                page=int(match.group("page")),
                condition=(match.group("condition") or "").strip() or None,
            )
        )
    return citations


def _passage_text(passage: Any) -> str:
    """Read passage text from a dict or LangChain Document."""
    if isinstance(passage, dict):
        return str(passage.get("text") or "")
    return str(getattr(passage, "page_content", "") or "")


def _passage_key(passage: Any) -> tuple[str, int] | None:
    """Read the (source, page) identity of a passage."""
    if isinstance(passage, dict):
        source = passage.get("source") or passage.get("document")
        page = passage.get("page")
    else:
        metadata = getattr(passage, "metadata", {}) or {}
        source = metadata.get("source")
        page = metadata.get("page")
    if not source or page is None:
        return None
    try:
        return str(source), int(page)
    except (TypeError, ValueError):
        return None


def _answer_body(answer: str) -> str:
    """Strip citation markers and section headers from the prose under test."""
    text = str(answer or "")
    if "**Supporting excerpts**" in text:
        text = text.split("**Supporting excerpts**", 1)[0]
    elif "**Condition-specific guidance**" in text:
        text = text.split("**Condition-specific guidance**", 1)[1]

    text = _CITATION_RE.sub("", text)
    lines: list[str] = []
    for line in text.splitlines():
        if _HEADER_RE.match(line):
            continue
        cleaned = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
        if cleaned:
            lines.append(cleaned)
    return " ".join(lines).strip()


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(str(text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _numbers(text: str) -> set[str]:
    return {number.replace(",", "") for number in _NUMBER_RE.findall(str(text or ""))}


def verify_citations(answer: str, passages: Iterable[Any]) -> CitationReport:
    """Verify an answer against the passages supplied as evidence.

    ``passages`` items may be dicts with ``source``/``page``/``text`` keys or
    LangChain ``Document`` objects with equivalent metadata.
    """
    passage_list = list(passages)
    citations = parse_citations(answer)
    issues: list[str] = []
    unsupported: list[str] = []

    if not citations:
        issues.append("Answer contains no source citations.")

    by_key: dict[tuple[str, int], list[str]] = {}
    for passage in passage_list:
        key = _passage_key(passage)
        if key is None:
            continue
        by_key.setdefault(key, []).append(_passage_text(passage))

    cited_texts: list[str] = []
    for citation in citations:
        key = (citation.source, citation.page)
        matches = by_key.get(key, [])
        if not matches:
            issues.append(
                f"Citation points to unknown passage: {citation.source}, page {citation.page}."
            )
        else:
            cited_texts.extend(matches)

    cited_corpus = "\n".join(cited_texts)
    cited_tokens = _tokens(cited_corpus)
    cited_numbers = _numbers(cited_corpus)

    body = _answer_body(answer)
    if not body:
        issues.append("Answer body is empty after removing citations.")
    else:
        body_numbers = _numbers(body)
        missing_numbers = sorted(number for number in body_numbers if number not in cited_numbers)
        if missing_numbers:
            issues.append("Numeric claims absent from cited passages: " + ", ".join(missing_numbers))

        for sentence in re.split(r"(?<=[.!?])\s+", body):
            sentence = sentence.strip()
            if len(sentence) < 25:
                continue
            tokens = _tokens(sentence)
            overlap = len(tokens & cited_tokens) / len(tokens) if tokens else 0.0
            numbers = _numbers(sentence)
            numbers_backed = bool(numbers) and numbers.issubset(cited_numbers)
            if overlap < 0.20 and not numbers_backed:
                unsupported.append(sentence[:180])

    if unsupported:
        issues.append(f"{len(unsupported)} claim(s) are not grounded in the cited passages.")

    return CitationReport(
        verified=not issues,
        citations_checked=len(citations),
        supported_claims=max(len(body.split(".")) - 1, 0),
        issues=issues,
        unsupported_claims=unsupported,
    )


def format_verification(report: CitationReport) -> str:
    """Render a compact verification line suitable for appending to an answer."""
    if report.verified:
        return (
            f"**Citation check:** PASS — {report.citations_checked} citation(s) verified "
            f"against retrieved passages."
        )
    detail = " ".join(report.issues)
    return f"**Citation check:** REVIEW — {detail}"
