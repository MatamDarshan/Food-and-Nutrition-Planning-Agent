"""
rag/document_sources.py
-----------------------
Declarative manifest for every PDF in the nutrition knowledge base.

The manifest is the single source of truth for document provenance and the
health conditions a document is relevant to.  It is deliberately small and
dependency-free so the ingestion CLI, the retriever and the tests can all use
it without importing PDF loaders or embedding models.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CORE_COLLECTION = "core"
CONDITION_COLLECTION = "conditions"


@dataclass(frozen=True)
class DocumentSource:
    """Metadata describing one trusted reference document."""

    filename: str
    collection: str
    title: str
    conditions: tuple[str, ...]
    provenance: str

    @property
    def primary_condition(self) -> str:
        """The canonical tag used for metadata filtering."""
        return self.conditions[0] if self.conditions else "general"


def _source(
    filename: str,
    collection: str,
    title: str,
    conditions: tuple[str, ...],
    provenance: str,
) -> DocumentSource:
    return DocumentSource(
        filename=filename,
        collection=collection,
        title=title,
        conditions=conditions,
        provenance=provenance,
    )


ICMR_SOURCE = _source(
    filename="ICMR_NIN_Dietary_Guidelines_for_Indians.pdf",
    collection=CORE_COLLECTION,
    title="ICMR-NIN Dietary Guidelines for Indians",
    conditions=("general",),
    provenance=(
        "Generated locally by knowledge_base/build_sample_documents.py from "
        "ICMR-NIN (National Institute of Nutrition, Hyderabad) dietary guidance."
    ),
)

CONDITION_SOURCES: dict[str, DocumentSource] = {
    item.filename: item
    for item in [
        _source(
            filename="PCOS-Guideline-Summary-2023.pdf",
            collection=CONDITION_COLLECTION,
            title="International Evidence-Based Guideline for PCOS (2023 summary)",
            conditions=("pcos",),
            provenance="2023 international PCOS guideline summary; bundled as a public reference document.",
        ),
        _source(
            filename="ThyroidDietReport.pdf",
            collection=CONDITION_COLLECTION,
            title="Clinical Perspectives on Nutritional Management of Thyroid Disease",
            conditions=("thyroid", "hypothyroidism"),
            provenance="Public clinical nutrition reference report on thyroid modulation.",
        ),
        _source(
            filename="HypertensionDietReport.pdf",
            collection=CONDITION_COLLECTION,
            title="Comprehensive Clinical Strategy for Hypertension Management",
            conditions=("hypertension", "blood_pressure"),
            provenance="Public clinical nutrition reference report on hypertension management.",
        ),
        _source(
            filename="LactoseIntolerance DietaryPlanningReport.pdf",
            collection=CONDITION_COLLECTION,
            title="Lactose Intolerance: Dietary Habits and Nutrition Planning",
            conditions=("lactose_intolerance", "lactose"),
            provenance="Public clinical nutrition reference report on lactose intolerance.",
        ),
        _source(
            filename="obesity_report.pdf",
            collection=CONDITION_COLLECTION,
            title="Directorate General of Health Services: Obesity Report",
            conditions=("obesity", "weight_management"),
            provenance="DGHS (India) quarterly newsletter issue on obesity, April 2024.",
        ),
        _source(
            filename="healthy_sleep.pdf",
            collection=CONDITION_COLLECTION,
            title="Your Guide to Healthy Sleep",
            conditions=("sleep", "insomnia"),
            provenance="Public healthy-sleep guide; sleep is a modifiable nutrition-adjacent lifestyle factor.",
        ),
    ]
}

ALL_SOURCES: dict[str, DocumentSource] = {
    ICMR_SOURCE.filename: ICMR_SOURCE,
    **CONDITION_SOURCES,
}

# User-facing spellings mapped to the canonical tags in the manifest.
_CONDITION_ALIASES: dict[str, str] = {
    "pcos": "pcos",
    "polycystic ovary syndrome": "pcos",
    "thyroid": "thyroid",
    "hypothyroid": "thyroid",
    "hypothyroidism": "thyroid",
    "hypertension": "hypertension",
    "high blood pressure": "hypertension",
    "blood pressure": "hypertension",
    "lactose": "lactose_intolerance",
    "lactose intolerance": "lactose_intolerance",
    "lactose_intolerance": "lactose_intolerance",
    "obesity": "obesity",
    "weight loss": "obesity",
    "weight management": "obesity",
    "sleep": "sleep",
    "insomnia": "sleep",
    "healthy sleep": "sleep",
}


def normalise_condition(value: str) -> str:
    """Map a user-facing condition name to its canonical metadata tag."""
    key = " ".join(str(value or "").strip().lower().replace("-", " ").split())
    return _CONDITION_ALIASES.get(key, key.replace(" ", "_"))


def source_for(file_path: Path) -> Optional[DocumentSource]:
    """Look up the manifest entry for a PDF path, if one exists."""
    return ALL_SOURCES.get(Path(file_path).name)


def metadata_for(file_path: Path) -> dict[str, object]:
    """Return manifest-derived metadata for a PDF, or an empty dict if unknown.

    Only additive keys are returned; ``source``, ``page`` and ``file_path`` are
    always owned by the PDF loader so citation output stays consistent.
    """
    entry = source_for(file_path)
    if entry is None:
        return {}
    return {
        "collection": entry.collection,
        "doc_id": Path(entry.filename).stem,
        "title": entry.title,
        "condition": entry.primary_condition,
        "conditions": list(entry.conditions),
        "provenance": entry.provenance,
    }


def known_conditions() -> tuple[str, ...]:
    """Return the sorted set of canonical condition tags in the manifest."""
    tags = {tag for entry in ALL_SOURCES.values() for tag in entry.conditions}
    return tuple(sorted(tags))
