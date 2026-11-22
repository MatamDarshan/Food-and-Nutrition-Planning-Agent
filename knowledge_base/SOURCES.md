# Knowledge-base sources and provenance

The RAG layer uses two **separate** FAISS indexes so that adding reference
documents can never silently change the answers or benchmark scores of the
original ICMR-NIN index.

| Collection | PDF directory | Persisted index | Used by |
|---|---|---|---|
| `core` | `nutrition_documents/` | `faiss_index/` | Existing chat tool and the 16-query RAG benchmark |
| `conditions` | `condition_documents/` | `condition_faiss_index/` | `rag.condition_retriever` and future hybrid retrieval |

## Core collection

- **ICMR_NIN_Dietary_Guidelines_for_Indians.pdf** — generated locally by
  `knowledge_base/build_sample_documents.py`. It is a curated demonstration
  summary of ICMR-NIN guidance, not the official publication. Replace it with
  the official PDF for production and rebuild with
  `python -m rag.ingest --collection core --rebuild`.

## Condition collection

These six public reference PDFs were bundled from the public
[NutriGen AI](https://github.com/RitamRixx/NutriGen_AI) repository (MIT license,
copyright (c) 2026 Ritam Rakshit). They are included for educational and
research use; they are **not** clinical advice. Verify all guidance against the
primary publisher before using it in a real nutrition plan.

| File | Canonical condition tag(s) | Subject |
|---|---|---|
| `PCOS-Guideline-Summary-2023.pdf` | `pcos` | 2023 international PCOS assessment and management guideline summary |
| `ThyroidDietReport.pdf` | `thyroid`, `hypothyroidism` | Nutritional modulation and dietary management of thyroid disease |
| `HypertensionDietReport.pdf` | `hypertension`, `blood_pressure` | Clinical strategy for hypertension management |
| `LactoseIntolerance DietaryPlanningReport.pdf` | `lactose_intolerance`, `lactose` | Lactose intolerance and meal planning |
| `obesity_report.pdf` | `obesity`, `weight_management` | DGHS (India) newsletter on obesity |
| `healthy_sleep.pdf` | `sleep`, `insomnia` | Healthy-sleep guide (sleep as a lifestyle factor) |

The tags above live in `rag/document_sources.py`. Every indexed chunk carries
`source`, `page`, `collection`, `condition`, `conditions`, `doc_id` and
`provenance` metadata, which makes citations verifiable and lets retrieval
filter by condition.

## Rebuilding an index

```bash
# Inspect the manifest without downloading or embedding anything heavy
python -m rag.ingest --collection conditions --dry-run

# Build/replace the condition index (local embeddings, no API key required)
python -m rag.ingest --collection conditions --rebuild

# Build both collections into one experimental index
python -m rag.ingest --collection all --index-dir ./tmp_index --rebuild
```

The first build parses ~200 PDF pages and runs the local MiniLM encoder, so it
takes a few minutes on CPU. Subsequent starts only load the persisted index.
