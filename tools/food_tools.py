"""
tools/food_tools.py
-------------------
Tools 2 – 5 for the AI Food & Nutrition Planning Agent.

Tool 2 — search_food_database
Tool 3 — calculate_meal_nutrition
Tool 4 — find_food_substitutes
Tool 5 — validate_meal_plan

Design notes
------------
* The CSV is loaded once per process via a module-level cache dict (_CACHE).
* All Pandas filtering uses vectorised boolean masks — no row iteration.
* Tool 4 ranks substitutes by cosine similarity on the macro vector
  [calories, protein, carbs, fats, fiber], giving nutritionally close matches.
* Tools 3 and 5 accept complex nested data as JSON strings so Gemini's
  function-calling layer can produce them without deeply nested schemas.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from langchain_core.tools import tool

from config.settings import settings
from core.allergens import (
    canonicalize_allergens,
    parse_food_allergens,
    ingredients_contain_allergen,
    food_violates_exclusion,
)
from core.validation import run_all_checks

# ── Dataset loader (singleton) ────────────────────────────────────────────────

_CACHE: dict[str, pd.DataFrame] = {}
_DEFAULT_CSV_PATH = Path(__file__).parent.parent / "data" / "food_data.csv"

MACRO_COLS = ["calories", "protein", "carbohydrates", "fats", "fiber"]


def _get_df() -> pd.DataFrame:
    """Return the food DataFrame, loading and caching it on first call."""
    if "df" not in _CACHE:
        path = Path(settings.food_csv_path)
        if not path.exists():
            path = _DEFAULT_CSV_PATH
        _CACHE["df"] = pd.read_csv(path)
    return _CACHE["df"]


# ── Shared filter helpers ─────────────────────────────────────────────────────

def _diet_mask(df: pd.DataFrame, diet_type: str) -> pd.Series:
    """
    'veg' users see only veg items.
    'non-veg' users see both veg and non-veg.
    """
    if diet_type == "veg":
        return df["diet_type"] == "veg"
    return pd.Series([True] * len(df), index=df.index)


def _allergen_mask(df: pd.DataFrame, allergies: list[str]) -> pd.Series:
    """Exclude rows containing any of the user's allergens in tag or ingredients.

    Uses canonicalisation in ``core.allergens`` and checks both allergen tags and
    individual ingredients within composite dishes.
    """
    if not allergies:
        return pd.Series([True] * len(df), index=df.index)
    user_allergens = canonicalize_allergens(allergies)
    if not user_allergens:
        return pd.Series([True] * len(df), index=df.index)

    food_allergens = df["allergens"].map(parse_food_allergens)
    tag_violation = food_allergens.map(lambda tags: bool(tags & user_allergens))

    ing_col = df["ingredients"] if "ingredients" in df.columns else pd.Series([""] * len(df), index=df.index)
    ing_violation = ing_col.map(lambda ing: bool(ingredients_contain_allergen(ing, allergies)))

    return ~(tag_violation | ing_violation)


def _excluded_mask(df: pd.DataFrame, excluded_foods: list[str]) -> pd.Series:
    """Exclude rows whose food_name, variant, or ingredients violate user exclusions."""
    if not excluded_foods:
        return pd.Series([True] * len(df), index=df.index)

    def is_violated(row: pd.Series) -> bool:
        fname = str(row.get("food_name", ""))
        ing = row.get("ingredients", "")
        violated, _ = food_violates_exclusion(fname, ing, excluded_foods)
        return violated

    return ~df.apply(is_violated, axis=1)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity in [0, 1] between two vectors."""
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — Food Database Search
# ─────────────────────────────────────────────────────────────────────────────

@tool
def search_food_database(
    diet_type: str,
    meal_type: str,
    allergies: list[str],
    excluded_foods: list[str],
    max_calories: float = 9999.0,
    category: str = "",
    top_n: int = 8,
) -> str:
    """Search the Indian food database and return matching food items.

    Applies vectorised Pandas filters for diet type, meal slot, allergens,
    excluded foods, calorie cap, and optional category — then returns up
    to top_n results.

    Args:
        diet_type: 'veg' returns only vegetarian items.
                   'non-veg' returns both vegetarian and non-vegetarian.
        meal_type: One of breakfast | lunch | snack | dinner.
        allergies: Allergen tags to exclude, e.g. ['gluten', 'dairy'].
                   Use an empty list if no restrictions.
        excluded_foods: Food names to exclude, e.g. ['Samosa'].
                        Use an empty list if none.
        max_calories: Maximum calories per 100 g (default: no cap).
        category: Filter by food category — Grain | Dairy | Legume | Meat |
                  Vegetable | Fruit | Snack | Beverage. Empty string = all.
        top_n: Number of results to return (default: 8, max recommended: 15).

    Returns:
        JSON string — a list of food item objects, each containing:
            food_id, food_name, calories, protein, carbohydrates, fats,
            fiber, diet_type, meal_type, food_category, ingredients,
            allergens, glycemic_index.
        Returns an error JSON object on failure.
    """
    try:
        df = _get_df()

        # ── apply filters ──────────────────────────────────────────────────
        mask = (
            _diet_mask(df, diet_type)
            & df["meal_type"].str.contains(meal_type, regex=False, na=False)
            & (df["calories"] <= max_calories)
            & _allergen_mask(df, allergies)
            & _excluded_mask(df, excluded_foods)
        )
        if category:
            mask = mask & (df["food_category"].str.lower() == category.lower())

        results = df[mask].head(top_n)

        if results.empty:
            return json.dumps(
                {"message": "No foods found matching the given criteria.", "items": []}
            )

        return json.dumps(
            {"items": results.to_dict(orient="records"), "count": len(results)},
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — Meal Nutrition Calculator
# ─────────────────────────────────────────────────────────────────────────────

@tool
def calculate_meal_nutrition(items_json: str) -> str:
    """Calculate the total nutritional value of a meal from food names and quantities.

    Looks up each food item in the database, scales the per-100 g values to
    the specified quantity, and returns aggregate totals plus a per-item breakdown.

    Args:
        items_json: A JSON array string where each element is an object with:
            - "food_name" (str): Exact name as it appears in the database.
            - "quantity_g" (float): Quantity in grams.
            Example:
            '[{"food_name": "Idli", "quantity_g": 150},
              {"food_name": "Sambar", "quantity_g": 100}]'

    Returns:
        JSON string containing:
            total_calories, total_protein, total_carbs, total_fats,
            total_fiber (all as floats), and a 'breakdown' list with
            per-item contributions.
        Returns an error JSON object if a food name is not found.
    """
    try:
        parsed = json.loads(items_json)
        if not isinstance(parsed, list):
            return json.dumps({"error": "items_json must be a JSON array."})
        items: list[dict] = [item for item in parsed if isinstance(item, dict)]
        if not items:
            return json.dumps({"error": "items_json contains no valid food entries."})

        df = _get_df()
        name_index: dict[str, dict] = (
            df.assign(_key=df["food_name"].str.lower())
            .set_index("_key")[MACRO_COLS]
            .to_dict(orient="index")
        )
        canonical_names: dict[str, str] = (
            df.assign(_key=df["food_name"].str.lower())
            .set_index("_key")["food_name"]
            .to_dict()
        )

        totals = dict.fromkeys(
            ["total_calories", "total_protein", "total_carbs", "total_fats", "total_fiber"],
            0.0,
        )
        breakdown: list[dict] = []

        for item in items:
            raw_name = str(item.get("food_name", "")).strip()
            key = raw_name.lower()
            food_name = canonical_names.get(key, raw_name)
            try:
                qty_g = float(item.get("quantity_g", 0))
            except (TypeError, ValueError):
                qty_g = 0.0

            if key not in name_index:
                return json.dumps(
                    {"error": f"Food '{raw_name}' not found in the database."}
                )
            if qty_g <= 0:
                return json.dumps(
                    {"error": f"Quantity for '{raw_name}' must be greater than 0 g."}
                )

            row = name_index[key]
            scale = qty_g / 100.0
            item_nutrition = {
                "food_name": food_name,
                "quantity_g": qty_g,
                "calories": round(row["calories"] * scale, 1),
                "protein": round(row["protein"] * scale, 1),
                "carbs": round(row["carbohydrates"] * scale, 1),
                "fats": round(row["fats"] * scale, 1),
                "fiber": round(row["fiber"] * scale, 1),
            }
            breakdown.append(item_nutrition)

            totals["total_calories"] += item_nutrition["calories"]
            totals["total_protein"] += item_nutrition["protein"]
            totals["total_carbs"] += item_nutrition["carbs"]
            totals["total_fats"] += item_nutrition["fats"]
            totals["total_fiber"] += item_nutrition["fiber"]

        # Round totals
        totals = {k: round(v, 1) for k, v in totals.items()}
        return json.dumps({**totals, "breakdown": breakdown}, indent=2)

    except json.JSONDecodeError:
        return json.dumps({"error": "items_json is not valid JSON."})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — Food Substitution Finder
# ─────────────────────────────────────────────────────────────────────────────

@tool
def find_food_substitutes(
    food_name: str,
    diet_type: str,
    meal_type: str,
    allergies: list[str],
    top_n: int = 3,
    excluded_foods: Optional[list[str]] = None,
) -> str:
    """Find the best nutritional substitutes for a given food item.

    Ranks candidates by cosine similarity on the macro vector
    [calories, protein, carbohydrates, fats, fiber], ensuring the
    substitutes match the user's diet type, meal slot, allergen
    restrictions, and personal food exclusions.

    Args:
        food_name: Exact name of the food to replace (e.g. 'Paneer').
        diet_type: 'veg' or 'non-veg' — same as the user's preference.
        meal_type: Meal context for the substitute
                   (breakfast | lunch | snack | dinner).
        allergies: Allergen tags to exclude from substitutes.
                   Use an empty list if no restrictions.
        top_n: Number of substitutes to return (default: 3).
        excluded_foods: Food names the user never wants suggested.

    Returns:
        JSON string with a 'substitutes' list, each item containing:
            food_id, food_name, similarity_score (0–1),
            calories, protein, carbohydrates, fats, fiber,
            diet_type, food_category, allergens.
        Returns an error JSON object if the original food is not found.
    """
    try:
        df = _get_df()

        # ── find original food ─────────────────────────────────────────────
        requested_name = str(food_name).strip()
        orig_rows = df[df["food_name"].str.strip().str.lower() == requested_name.lower()]
        if orig_rows.empty:
            return json.dumps(
                {"error": f"Food '{requested_name}' not found in the database."}
            )
        orig = orig_rows.iloc[0]
        orig_name = str(orig["food_name"])
        orig_vec = orig[MACRO_COLS].values.astype(float)

        # ── filter candidates ──────────────────────────────────────────────
        candidates = df[
            _diet_mask(df, diet_type)
            & df["meal_type"].str.contains(meal_type, regex=False, na=False)
            & _allergen_mask(df, allergies)
            & _excluded_mask(df, excluded_foods or [])
            & (df["food_name"].str.lower() != orig_name.lower())   # exclude itself
        ].copy()

        if candidates.empty:
            return json.dumps(
                {"message": "No substitutes found with the given constraints.", "substitutes": []}
            )

        # ── compute cosine similarity ──────────────────────────────────────
        candidates["similarity_score"] = candidates[MACRO_COLS].apply(
            lambda row: _cosine_similarity(orig_vec, row.values.astype(float)),
            axis=1,
        )

        top = (
            candidates.nlargest(top_n, "similarity_score")[
                ["food_id", "food_name", "similarity_score"] + MACRO_COLS
                + ["diet_type", "food_category", "allergens"]
            ]
            .round({"similarity_score": 3})
        )

        return json.dumps(
            {"original_food": orig_name, "substitutes": top.to_dict(orient="records")},
            indent=2,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — Meal Plan Validator
# ─────────────────────────────────────────────────────────────────────────────

@tool
def validate_meal_plan(
    plan_json: str,
    diet_type: str,
    allergies: list[str],
    excluded_foods: list[str],
    calorie_target: float,
    protein_g: float,
    carbs_g: float,
    fats_g: float,
) -> str:
    """Validate a one-day meal plan against the user's dietary rules and targets.

    Runs the following checks:
      1. All required meals (breakfast, lunch, dinner) are present.
      2. All food quantities are positive.
      3. All foods match the user's diet type (veg/non-veg).
      4. No food contains a user allergen.
      5. No excluded food appears in the plan.
      6. Planned calories are within ±15 % of the daily calorie target.

    Args:
        plan_json: JSON object string with keys 'breakfast', 'lunch',
            'snack', 'dinner'. Each value is a list of food entries:
            {"food_name": str, "quantity_g": float}.
            Example:
            '{"breakfast": [{"food_name": "Idli", "quantity_g": 150},
                            {"food_name": "Sambar", "quantity_g": 100}],
              "lunch":     [{"food_name": "Dal Tadka", "quantity_g": 200},
                            {"food_name": "Basmati Rice", "quantity_g": 150}],
              "snack":     [{"food_name": "Apple", "quantity_g": 150}],
              "dinner":    [{"food_name": "Palak Paneer", "quantity_g": 200},
                            {"food_name": "Whole Wheat Roti", "quantity_g": 90}]}'
        diet_type: 'veg' or 'non-veg'.
        allergies: List of allergen tags (e.g. ['dairy', 'gluten']).
        excluded_foods: List of food names the user wants excluded.
        calorie_target: User's daily calorie goal in kcal.
        protein_g: User's daily protein target in grams.
        carbs_g: User's daily carbohydrate target in grams.
        fats_g: User's daily fat target in grams.

    Returns:
        JSON string containing:
            is_valid (bool), issues (list of str),
            calorie_deviation_pct (float),
            planned_calories, planned_protein, planned_carbs, planned_fats.
    """
    try:
        plan = json.loads(plan_json)
        df = _get_df()

        # ── calculate total planned nutrition via Tool 3 logic ─────────────
        name_index: dict[str, dict] = (
            df.assign(_key=df["food_name"].str.lower())
            .set_index("_key")[MACRO_COLS]
            .to_dict(orient="index")
        )
        planned = dict.fromkeys(MACRO_COLS, 0.0)
        if isinstance(plan, dict):
            for items in plan.values():
                if isinstance(items, dict):
                    items = [items]
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    key = str(item.get("food_name", "")).strip().lower()
                    try:
                        qty_g = float(item.get("quantity_g", 0))
                    except (TypeError, ValueError):
                        qty_g = 0.0
                    row = name_index.get(key)
                    if row and qty_g > 0:
                        scale = qty_g / 100.0
                        for col in MACRO_COLS:
                            planned[col] += row[col] * scale

        planned_calories = round(planned["calories"], 1)
        planned_protein = round(planned["protein"], 1)
        planned_carbs = round(planned["carbohydrates"], 1)
        planned_fats = round(planned["fats"], 1)

        # ── run all validation rules ───────────────────────────────────────
        issues, deviation_pct = run_all_checks(
            plan=plan,
            diet_type=diet_type,
            allergies=allergies,
            excluded_foods=excluded_foods,
            calorie_target=calorie_target,
            planned_calories=planned_calories,
            food_df=df,
        )

        return json.dumps(
            {
                "is_valid": len(issues) == 0,
                "issues": issues,
                "calorie_deviation_pct": deviation_pct,
                "planned_calories": planned_calories,
                "planned_protein": planned_protein,
                "planned_carbs": planned_carbs,
                "planned_fats": planned_fats,
                "target_calories": calorie_target,
                "target_protein": protein_g,
                "target_carbs": carbs_g,
                "target_fats": fats_g,
            },
            indent=2,
        )
    except json.JSONDecodeError:
        return json.dumps({"error": "plan_json is not valid JSON."})
    except Exception as exc:
        return json.dumps({"error": str(exc)})
