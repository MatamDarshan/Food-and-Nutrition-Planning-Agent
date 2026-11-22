"""
core/allergens.py
-----------------
Single source of truth for allergen handling.

The food database stores allergens as a pipe-separated string of canonical
tags (``dairy|tree_nuts``).  User profiles store canonical tags too, but the
LLM, forms, or future data sources may send synonyms (``milk``, ``egg``,
``groundnut``).  Both the search layer and the deterministic validator must
agree on what "contains an allergen" means, otherwise a food can be filtered
out of search yet accepted by validation (or vice-versa).

This module normalises every spelling to one canonical key and exposes a
single ``food_has_allergen`` predicate used by both layers.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

# canonical tag -> known synonyms (all lower-case)
ALLERGEN_SYNONYMS: dict[str, frozenset[str]] = {
    "dairy": frozenset({
        "dairy", "milk", "curd", "yogurt", "yoghurt", "paneer", "ghee",
        "butter", "cheese", "cream", "khoya", "lassi", "chaas", "raita",
    }),
    "gluten": frozenset({
        "gluten", "wheat", "maida", "atta", "roti", "bread", "semolina",
        "suji", "rava", "barley", "rye",
    }),
    "eggs": frozenset({"eggs", "egg"}),
    "fish": frozenset({"fish", "seafood"}),
    "tree_nuts": frozenset({
        "tree_nuts", "tree nut", "tree nuts", "nuts", "almond", "almonds",
        "cashew", "cashews", "walnut", "walnuts", "pistachio", "pistachios",
        "coconut",
    }),
    "peanuts": frozenset({"peanuts", "peanut", "groundnut", "groundnuts"}),
    "soy": frozenset({"soy", "soya", "soybean", "soybeans"}),
    "shellfish": frozenset({
        "shellfish", "shrimp", "prawn", "prawns", "crab", "lobster",
    }),
}

# reverse lookup: every synonym and canonical tag -> canonical tag
_SYNONYM_TO_CANONICAL: dict[str, str] = {}
for _canonical, _synonyms in ALLERGEN_SYNONYMS.items():
    _SYNONYM_TO_CANONICAL[_canonical] = _canonical
    for _synonym in _synonyms:
        _SYNONYM_TO_CANONICAL[_synonym] = _canonical

_SPLIT_RE = re.compile(r"[|;,]")
_WHITESPACE_RE = re.compile(r"[\s\-]+")


def canonicalize_allergen(tag: object) -> Optional[str]:
    """Return the canonical allergen key for a single tag, or ``None``."""
    if tag is None:
        return None
    normalised = _WHITESPACE_RE.sub("_", str(tag).strip().lower())
    if not normalised or normalised == "none":
        return None
    return _SYNONYM_TO_CANONICAL.get(normalised, normalised)


def canonicalize_allergens(tags: Iterable[object]) -> set[str]:
    """Return the set of canonical allergen keys for an iterable of tags."""
    result: set[str] = set()
    for tag in tags or []:
        canonical = canonicalize_allergen(tag)
        if canonical:
            result.add(canonical)
    return result


def parse_food_allergens(raw: object) -> set[str]:
    """Parse a food row's allergen field (``dairy|tree_nuts``) into canonical keys."""
    if raw is None:
        return set()
    text = str(raw).strip()
    if not text or text.lower() == "none":
        return set()
    # ``nan`` appears when a CSV cell is empty and read as float NaN.
    if text.lower() == "nan":
        return set()
    return canonicalize_allergens(_SPLIT_RE.split(text))


def food_has_allergen(raw_food_allergens: object, allergies: Iterable[object]) -> bool:
    """True when a food's allergen tags overlap the user's allergen set."""
    food_set = parse_food_allergens(raw_food_allergens)
    if not food_set:
        return False
    return bool(food_set & canonicalize_allergens(allergies))


def parse_ingredients_list(raw_ingredients: object) -> list[str]:
    """Parse a semicolon or comma-separated ingredients string into lower-case tokens."""
    if raw_ingredients is None:
        return []
    text = str(raw_ingredients).strip()
    if not text or text.lower() in {"none", "nan"}:
        return []
    return [token.strip().lower() for token in _SPLIT_RE.split(text) if token.strip()]


def ingredients_contain_allergen(
    raw_ingredients: object,
    allergies: Iterable[object],
) -> Optional[str]:
    """Check if any ingredient in a composite food matches an allergen synonym.

    Returns the offending ingredient string if found, else None.
    """
    user_canonical = canonicalize_allergens(allergies)
    if not user_canonical:
        return None

    # Collect all search terms for the user's allergens
    target_terms: set[str] = set()
    for canonical in user_canonical:
        target_terms.update(ALLERGEN_SYNONYMS.get(canonical, {canonical}))

    for ingredient in parse_ingredients_list(raw_ingredients):
        # Match either exact token or sub-word (e.g. "whole wheat flour" contains "wheat")
        ing_words = set(re.findall(r"\b[a-z]+\b", ingredient))
        if ing_words & target_terms:
            return ingredient
        for term in target_terms:
            if re.search(rf"\b{re.escape(term)}\b", ingredient):
                return ingredient
    return None


def _stem_term(term: str) -> str:
    """Simple singular/plural normalizer for food terms (e.g. 'eggs' -> 'egg', 'idlis' -> 'idli')."""
    t = term.strip().lower()
    if t.endswith("ies") and len(t) > 4:
        return t[:-3] + "y"
    if t.endswith("es") and len(t) > 3:
        return t[:-2]
    if t.endswith("s") and not t.endswith("ss") and len(t) > 2:
        return t[:-1]
    return t


def food_violates_exclusion(
    food_name: str,
    raw_ingredients: object,
    excluded_foods: Iterable[str],
) -> tuple[bool, Optional[str]]:
    """Check if a food item or any of its composite ingredients violates user exclusions.

    Handles:
    - Exact name matching (case-insensitive)
    - Substring / word-boundary matching (e.g. 'Idli' excludes 'Steamed Idli', 'Idli with Sambar')
    - Singular / plural handling (e.g. 'Eggs' excludes 'Egg Curry', 'Egg Bhurji', 'Boiled Egg')
    - Ingredient matching within composite dishes (e.g. 'egg', 'semolina', 'onion')

    Returns (is_violated, matched_term_or_ingredient).
    """
    if not excluded_foods:
        return False, None

    fname_lower = food_name.strip().lower()
    fname_words = set(re.findall(r"\b[a-z0-9]+\b", fname_lower))
    fname_stems = {_stem_term(w) for w in fname_words}

    ingredients = parse_ingredients_list(raw_ingredients)

    for ex in excluded_foods:
        ex_raw = str(ex).strip().lower()
        if not ex_raw:
            continue
        ex_stem = _stem_term(ex_raw)

        # 1. Exact match
        if fname_lower == ex_raw or fname_lower == ex_stem:
            return True, ex

        # 2. Food name word match or stem match (e.g. 'eggs' -> stem 'egg' matches in 'egg curry')
        if ex_stem in fname_stems or ex_raw in fname_words:
            return True, ex

        # 3. Substring with word boundary in food name
        if re.search(rf"\b{re.escape(ex_stem)}\b", fname_lower) or re.search(rf"\b{re.escape(ex_raw)}\b", fname_lower):
            return True, ex

        # 4. Check composite food ingredients
        for ing in ingredients:
            ing_words = set(re.findall(r"\b[a-z0-9]+\b", ing))
            ing_stems = {_stem_term(w) for w in ing_words}
            if ex_raw in ing_words or ex_stem in ing_stems:
                return True, f"{ing} (in {food_name})"
            if re.search(rf"\b{re.escape(ex_stem)}\b", ing) or re.search(rf"\b{re.escape(ex_raw)}\b", ing):
                return True, f"{ing} (in {food_name})"

    return False, None

