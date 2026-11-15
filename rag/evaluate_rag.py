"""
rag/evaluate_rag.py
-------------------
Comprehensive RAG evaluation script testing 16 representative queries
(11 nutrition topic queries across all ICMR-NIN chapters + 5 irrelevant queries).
Measures:
- Retrieval relevance
- Euclidean vector distance
- Document and page source attribution
- Factual grounding in retrieved passages
- Clean irrelevant-query rejection
"""

import sys
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rag.retriever import retrieve_nutrition_knowledge, retrieve_with_details, MAX_RELEVANCE_DISTANCE

EVALUATION_QUERIES = [
    {
        "id": "Q01",
        "topic": "Millets",
        "query": "What are the nutritional benefits of finger millet (ragi) and pearl millet (bajra)?",
        "expected_relevant": True,
        "expected_page": 1,
        "expected_facts": ["ragi", "344", "calcium", "bajra", "iron"],
        "expected_summary": "Ragi calcium (344 mg/100g), Bajra iron (8 mg/100g) and zinc.",
    },
    {
        "id": "Q02",
        "topic": "Protein-rich Indian foods",
        "query": "Which Indian food items are the richest vegetarian and non-vegetarian sources of protein?",
        "expected_relevant": True,
        "expected_page": 1,
        "expected_facts": ["protein", "paneer", "dal", "pulses", "chicken", "eggs"],
        "expected_summary": "Paneer (18g/100g), Pulses (20-25g), Chicken (25g), Eggs (6g, PDCAAS 1.0).",
    },
    {
        "id": "Q03",
        "topic": "Dietary fibre",
        "query": "What is the recommended daily intake of dietary fibre and how does soluble fibre differ from insoluble fibre?",
        "expected_relevant": True,
        "expected_page": 3,
        "expected_facts": ["30g", "40g", "soluble", "insoluble", "pectin", "cellulose"],
        "expected_summary": "30-40g/day RDA, soluble forms gel lowering LDL, insoluble adds bulk.",
    },
    {
        "id": "Q04",
        "topic": "Whole grains versus refined grains",
        "query": "What are the anatomical and nutritional differences between whole wheat atta and refined maida?",
        "expected_relevant": True,
        "expected_page": 3,
        "expected_facts": ["bran", "germ", "endosperm", "fiber", "maida"],
        "expected_summary": "Whole grain preserves bran and germ; refined maida strips them leaving endosperm.",
    },
    {
        "id": "Q05",
        "topic": "Calcium",
        "query": "What are the top dietary sources of calcium in Indian diets and what is the adult RDA?",
        "expected_relevant": True,
        "expected_page": 4,
        "expected_facts": ["1,000", "calcium", "ragi", "til", "sesame", "milk"],
        "expected_summary": "1,000 mg/day RDA, Ragi (344mg), Sesame/Til (1450mg), milk/paneer.",
    },
    {
        "id": "Q06",
        "topic": "Iron",
        "query": "What is the recommended daily allowance for iron in Indian adults and how can non-heme iron absorption be enhanced?",
        "expected_relevant": True,
        "expected_page": 4,
        "expected_facts": ["iron", "19", "29", "vitamin c", "bajra"],
        "expected_summary": "19 mg (men), 29 mg (women); enhanced 2-3x by Vitamin C (lemon/amla).",
    },
    {
        "id": "Q07",
        "topic": "Vitamin B12",
        "query": "Why is Vitamin B12 important and what are its primary dietary sources for Indian vegetarians?",
        "expected_relevant": True,
        "expected_page": 4,
        "expected_facts": ["b12", "cobalamin", "2.2", "milk", "dairy", "vegan"],
        "expected_summary": "2.2-2.5 mcg RDA, RBC formation; sole vegetarian source is dairy.",
    },
    {
        "id": "Q08",
        "topic": "Healthy fats",
        "query": "What are the ICMR-NIN recommendations for visible cooking oils and fatty acid balance?",
        "expected_relevant": True,
        "expected_page": 4,
        "expected_facts": ["20g", "30g", "visible fat", "mufa", "pufa", "trans fat"],
        "expected_summary": "20-30g/day visible fat, 1:1:1 SFA:MUFA:PUFA balance, zero trans fats.",
    },
    {
        "id": "Q09",
        "topic": "Carbohydrates",
        "query": "What percentage of daily calories should come from carbohydrates according to ICMR-NIN?",
        "expected_relevant": True,
        "expected_page": 5,
        "expected_facts": ["50%", "55%", "carbohydrate", "complex", "sugar"],
        "expected_summary": "50% to 55% of daily energy from complex carbohydrates, simple sugars < 5%.",
    },
    {
        "id": "Q10",
        "topic": "Pulses and legumes",
        "query": "What role do pulses and legumes like chana, rajma, and moong dal play in Indian protein intake?",
        "expected_relevant": True,
        "expected_page": 1,
        "expected_facts": ["pulses", "chana", "rajma", "dal", "protein"],
        "expected_summary": "20-25g protein per 100g dry weight, rich in lysine.",
    },
    {
        "id": "Q11",
        "topic": "Food combinations",
        "query": "Explain the concept of cereal-pulse synergy and food combinations that enhance nutrient absorption.",
        "expected_relevant": True,
        "expected_page": 1,
        "expected_facts": ["synergy", "4:1", "5:1", "lysine", "methionine"],
        "expected_summary": "4:1 to 5:1 cereal-pulse ratio provides complete amino acids.",
    },
    {
        "id": "Q12",
        "topic": "Irrelevant general knowledge (Cricket)",
        "query": "Who won the ICC Men's Cricket World Cup in 2024?",
        "expected_relevant": False,
        "expected_page": None,
        "expected_facts": [],
        "expected_summary": "Non-nutrition query; should be cleanly rejected by distance threshold.",
    },
    {
        "id": "Q13",
        "topic": "Irrelevant general knowledge (Space)",
        "query": "What rocket was used by NASA to launch the Apollo 11 lunar mission?",
        "expected_relevant": False,
        "expected_page": None,
        "expected_facts": [],
        "expected_summary": "Non-nutrition query; should be cleanly rejected by distance threshold.",
    },
    {
        "id": "Q14",
        "topic": "Irrelevant general knowledge (Automotive)",
        "query": "How do you change the engine transmission fluid in a Honda Civic car?",
        "expected_relevant": False,
        "expected_page": None,
        "expected_facts": [],
        "expected_summary": "Non-nutrition query; should be cleanly rejected by distance threshold.",
    },
    {
        "id": "Q15",
        "topic": "Irrelevant general knowledge (Geography)",
        "query": "What is the capital city of Australia and what is its total population?",
        "expected_relevant": False,
        "expected_page": None,
        "expected_facts": [],
        "expected_summary": "Non-nutrition query; should be cleanly rejected by distance threshold.",
    },
    {
        "id": "Q16",
        "topic": "Irrelevant general knowledge (Software)",
        "query": "How do you configure a reverse proxy in Nginx with SSL certificates?",
        "expected_relevant": False,
        "expected_page": None,
        "expected_facts": [],
        "expected_summary": "Non-nutrition query; should be cleanly rejected by distance threshold.",
    },
]


def run_evaluation() -> list[dict[str, Any]]:
    """Execute evaluation over all 16 queries and return structured evaluation results."""
    results = []

    for item in EVALUATION_QUERIES:
        query = item["query"]
        details = retrieve_with_details(query=query, k=3, max_distance=MAX_RELEVANCE_DISTANCE)

        top_chunk = details[0] if details else None
        top_dist = top_chunk["distance"] if top_chunk else 9.99
        is_relevant = top_chunk["is_relevant"] if top_chunk else False
        retrieved_doc = top_chunk["document"] if (top_chunk and is_relevant) else "None"
        retrieved_page = top_chunk["page"] if (top_chunk and is_relevant) else "None"
        retrieved_text = top_chunk["text"] if (top_chunk and is_relevant) else ""

        # Aggregate all relevant retrieved chunks (k=3) for context grounding
        relevant_chunks = [c for c in details if c["is_relevant"]]
        combined_text = " \n\n ".join(c["text"] for c in relevant_chunks)

        # Relevance evaluation
        relevance_correct = is_relevant == item["expected_relevant"]

        # Attribution evaluation
        if item["expected_relevant"]:
            attribution_correct = (
                retrieved_doc == "ICMR_NIN_Dietary_Guidelines_for_Indians.pdf"
                and retrieved_page in [1, 2, 3, 4, 5]
            )
            # Grounding check across all retrieved passages
            text_lower = combined_text.lower()
            grounding_matches = [f for f in item["expected_facts"] if f.lower() in text_lower]
            grounding_pass = len(grounding_matches) >= 2
        else:
            attribution_correct = not is_relevant
            grounding_pass = not is_relevant

        overall_status = "PASS" if (relevance_correct and attribution_correct and grounding_pass) else "FAIL"

        results.append({
            "id": item["id"],
            "topic": item["topic"],
            "query": query,
            "expected_relevant": item["expected_relevant"],
            "expected_summary": item["expected_summary"],
            "retrieved_doc": retrieved_doc,
            "retrieved_page": retrieved_page,
            "retrieval_distance": top_dist,
            "is_relevant": is_relevant,
            "relevance_correct": relevance_correct,
            "attribution_correct": attribution_correct,
            "grounding_pass": grounding_pass,
            "status": overall_status,
            "retrieved_snippet": (retrieved_text[:120] + "...") if retrieved_text else "None (Filtered out)",
        })

    return results


if __name__ == "__main__":
    eval_results = run_evaluation()
    print("=" * 80)
    print("RAG EVALUATION REPORT — 16 REPRESENTATIVE QUERIES")
    print("=" * 80)
    for r in eval_results:
        print(f"[{r['id']}] {r['topic']}")
        print(f"  Query: {r['query']}")
        print(f"  Distance: {r['retrieval_distance']:.4f} | Relevant: {r['is_relevant']} (Expected: {r['expected_relevant']})")
        print(f"  Source: {r['retrieved_doc']}, Page {r['retrieved_page']}")
        print(f"  Snippet: {r['retrieved_snippet']}")
        print(f"  Status: {r['status']}")
        print("-" * 80)
