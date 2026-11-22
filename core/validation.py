"""
core/validation.py
------------------
Pure, side-effect-free validation functions for meal plan rule checking.
No I/O, no network, no global state — only Pandas DataFrame operations.

Called by Tool 5 (validate_meal_plan) and directly by the LangGraph
Meal Validation node.
"""

from __future__ import annotations

from typing import Iterator

import pandas as pd

from config.settings import settings
from core.allergens import (
    food_has_allergen,
    ingredients_contain_allergen,
    food_violates_exclusion,
)

# ── Constants ──────────────────────────────────────────────────────────────────
# Configurable via CALORIE_DEVIATION_THRESHOLD; defaults to ±15%.
CALORIE_DEVIATION_THRESHOLD = settings.calorie_deviation_threshold
REQUIRED_MEALS = ["breakfast", "lunch", "dinner"]
ALL_MEALS = ["breakfast", "lunch", "snack", "dinner"]
MACRO_COLS = ["calories", "protein", "carbohydrates", "fats", "fiber"]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _meal_items(plan: dict, meal: str) -> list[dict]:
    """Return the valid food-entry dicts for one meal slot.

    Defensive by design: LLM output occasionally contains a meal as a string,
    a single dict, or ``None``.  Validation must report that as an issue rather
    than raise ``AttributeError``.
    """
    if not isinstance(plan, dict):
        return []
    items = plan.get(meal, [])
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _iter_meal_items(plan: dict) -> Iterator[tuple[str, dict]]:
    """Yield ``(meal_name, food_entry)`` pairs for every valid entry."""
    for meal in ALL_MEALS:
        for item in _meal_items(plan, meal):
            yield meal, item


def _all_items(plan: dict) -> list[dict]:
    """Flatten all meal slots into a single list of food-entry dicts."""
    return [item for _, item in _iter_meal_items(plan)]


def _coerce_quantity(value: object) -> float:
    """Best-effort conversion of a quantity to float (0.0 when invalid)."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def check_plan_structure(plan: dict) -> list[str]:
    """Report malformed plan shapes instead of letting later checks crash."""
    if not isinstance(plan, dict):
        return [f"Meal plan must be a JSON object, got {type(plan).__name__}."]

    issues: list[str] = []
    for meal in ALL_MEALS:
        if meal not in plan:
            continue
        value = plan[meal]
        if value is None:
            continue
        if isinstance(value, dict):
            issues.append(f"Meal '{meal}' must be a list of food objects, got a single object.")
            continue
        if not isinstance(value, list):
            issues.append(
                f"Meal '{meal}' must be a list of food objects, got {type(value).__name__}."
            )
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                issues.append(
                    f"Meal '{meal}' entry #{index + 1} must be an object, "
                    f"got {type(item).__name__}."
                )
    return issues


# ── Individual rule checkers ──────────────────────────────────────────────────

def check_diet_compliance(
    plan: dict,
    diet_type: str,
    food_df: pd.DataFrame,
) -> list[str]:
    """Every food in the plan must match the user's diet type.

    A vegetarian user must not receive non-veg foods.
    A non-veg user may receive both veg and non-veg.
    """
    issues: list[str] = []
    name_to_diet: dict[str, str] = (
        food_df.assign(_key=food_df["food_name"].str.lower())
        .set_index("_key")["diet_type"]
        .to_dict()
    )
    for item in _all_items(plan):
        food_name = str(item.get("food_name", "")).strip()
        item_diet = name_to_diet.get(food_name.lower())
        if item_diet is None:
            issues.append(f"Food '{food_name}' was not found in the database.")
        elif diet_type == "veg" and item_diet == "non-veg":
            issues.append(
                f"'{food_name}' is non-vegetarian but the user follows a vegetarian diet."
            )
    return issues


def check_allergen_compliance(
    plan: dict,
    allergies: list[str],
    food_df: pd.DataFrame,
) -> list[str]:
    """No food in the plan may contain any of the user's allergens (checks tags AND composite ingredients)."""
    if not allergies:
        return []
    issues: list[str] = []
    name_to_info = (
        food_df.assign(_key=food_df["food_name"].str.lower())
        .set_index("_key")
        .to_dict(orient="index")
    )
    for item in _all_items(plan):
        food_name = str(item.get("food_name", "")).strip()
        row_info = name_to_info.get(food_name.lower(), {})
        raw_allergens = row_info.get("allergens", "none")
        raw_ingredients = row_info.get("ingredients", "")

        # 1. Check allergen tags
        if food_has_allergen(raw_allergens, allergies):
            issues.append(
                f"'{food_name}' contains an allergen that the user must avoid "
                f"({', '.join(str(a) for a in allergies)})."
            )
            continue

        # 2. Check composite ingredients
        offending_ing = ingredients_contain_allergen(raw_ingredients, allergies)
        if offending_ing:
            issues.append(
                f"'{food_name}' contains allergen ingredient '{offending_ing}' "
                f"which violates user's allergy ({', '.join(str(a) for a in allergies)})."
            )
    return issues


def check_excluded_foods(
    plan: dict,
    excluded_foods: list[str],
    food_df: Optional[pd.DataFrame] = None,
) -> list[str]:
    """No food name, variant, or ingredient that the user excluded may appear in the plan."""
    if not excluded_foods:
        return []
    issues: list[str] = []
    name_to_ingredients: dict[str, str] = {}
    if food_df is not None and "ingredients" in food_df.columns:
        name_to_ingredients = (
            food_df.assign(_key=food_df["food_name"].str.lower())
            .set_index("_key")["ingredients"]
            .fillna("")
            .to_dict()
        )

    for item in _all_items(plan):
        food_name = str(item.get("food_name", "")).strip()
        raw_ing = name_to_ingredients.get(food_name.lower(), "")
        violated, matched_term = food_violates_exclusion(food_name, raw_ing, excluded_foods)
        if violated:
            issues.append(
                f"'{food_name}' violates user exclusion: matches '{matched_term}'."
            )
    return issues


def check_meal_completeness(plan: dict) -> list[str]:
    """Breakfast, lunch, and dinner must each have at least one food item."""
    return [
        f"Meal plan is missing required meal: '{meal}'."
        for meal in REQUIRED_MEALS
        if not _meal_items(plan, meal)
    ]


def check_quantities(plan: dict) -> list[str]:
    """All food quantities must be positive numbers greater than zero."""
    issues: list[str] = []
    for meal, item in _iter_meal_items(plan):
        qty = _coerce_quantity(item.get("quantity_g", 0))
        if qty <= 0:
            issues.append(
                f"'{item.get('food_name', 'unknown')}' in {meal} "
                f"has an invalid quantity: {item.get('quantity_g', 0)} g."
            )
    return issues


def check_calorie_deviation(
    planned_calories: float,
    target_calories: float,
    threshold: float = CALORIE_DEVIATION_THRESHOLD,
) -> tuple[float, bool]:
    """
    Compute the signed percentage deviation of planned vs target calories.

    Returns
    -------
    deviation_pct : float
        Signed percentage deviation (positive = over target).
    within_threshold : bool
        True when |deviation| ≤ threshold.
    """
    if target_calories == 0:
        return 0.0, True
    deviation = (planned_calories - target_calories) / target_calories
    return round(deviation * 100, 2), abs(deviation) <= threshold


# ── Composite runner ──────────────────────────────────────────────────────────

def run_all_checks(
    plan: dict,
    diet_type: str,
    allergies: list[str],
    excluded_foods: list[str],
    calorie_target: float,
    planned_calories: float,
    food_df: pd.DataFrame,
) -> tuple[list[str], float]:
    """
    Run every validation rule and return all issues found.

    Returns
    -------
    issues : list[str]
        All rule violation messages (empty list = plan is valid).
    calorie_deviation_pct : float
        Signed % deviation for reporting.
    """
    if not isinstance(plan, dict):
        return [f"Meal plan must be a JSON object, got {type(plan).__name__}."], 0.0

    issues: list[str] = []
    issues += check_plan_structure(plan)
    issues += check_meal_completeness(plan)
    issues += check_quantities(plan)
    issues += check_diet_compliance(plan, diet_type, food_df)
    issues += check_allergen_compliance(plan, allergies, food_df)
    issues += check_excluded_foods(plan, excluded_foods, food_df)

    deviation_pct, within_threshold = check_calorie_deviation(
        planned_calories, calorie_target
    )
    if not within_threshold:
        issues.append(
            f"Calorie deviation of {deviation_pct:+.1f}% exceeds the "
            f"±{int(CALORIE_DEVIATION_THRESHOLD * 100)}% acceptable threshold "
            f"(planned: {planned_calories:.0f} kcal, target: {calorie_target:.0f} kcal)."
        )

    return issues, deviation_pct


# ── 7-Day Weekly Plan Validation ──────────────────────────────────────────────

REQUIRED_DAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


def run_weekly_checks(
    weekly_plan: dict,
    diet_type: str,
    allergies: list[str],
    excluded_foods: list[str],
    calorie_target: float,
    food_df: pd.DataFrame,
) -> tuple[list[str], float, dict[str, float]]:
    """
    Validate a complete 7-day Indian meal plan.

    Parameters
    ----------
    weekly_plan : dict
        Dict mapping day names ("monday".."sunday") to day meal dicts
        {"breakfast": [...], "lunch": [...], "snack": [...], "dinner": [...]}.
    diet_type : str
        "veg" or "non-veg".
    allergies : list[str]
        User's allergy tags.
    excluded_foods : list[str]
        Foods to exclude.
    calorie_target : float
        Target calories per day.
    food_df : pd.DataFrame
        Food database.

    Returns
    -------
    issues : list[str]
        List of all validation errors.
    avg_deviation_pct : float
        Weekly average calorie deviation percentage.
    daily_calories : dict[str, float]
        Planned calories per day.
    """
    issues: list[str] = []
    daily_calories: dict[str, float] = {}

    if not isinstance(weekly_plan, dict):
        return (
            [f"Weekly meal plan must be a JSON object, got {type(weekly_plan).__name__}."],
            0.0,
            {},
        )

    # Check that all 7 days exist
    normalized_plan: dict[str, dict] = {}
    for k, v in weekly_plan.items():
        if isinstance(v, dict):
            normalized_plan[str(k).lower().strip()] = v

    for day in REQUIRED_DAYS:
        if day not in normalized_plan:
            issues.append(f"7-day meal plan is missing required day: '{day.title()}'.")

    # Name-to-calorie mapping for fast calculation (case-insensitive keys)
    name_to_cal = (
        food_df.assign(_key=food_df["food_name"].str.lower())
        .set_index("_key")["calories"]
        .to_dict()
    )

    day_signatures: list[str] = []

    for day in REQUIRED_DAYS:
        day_meals = normalized_plan.get(day, {})
        if not day_meals:
            continue

        # Check required meals in each day
        for meal in REQUIRED_MEALS:
            if not _meal_items(day_meals, meal):
                issues.append(f"{day.title()} is missing required meal: '{meal}'.")

        # Validate items, dietary compliance, allergens, excluded foods for this day
        day_issues, _ = run_all_checks(
            plan=day_meals,
            diet_type=diet_type,
            allergies=allergies,
            excluded_foods=excluded_foods,
            calorie_target=calorie_target,
            planned_calories=calorie_target,  # check individual calorie deviation below
            food_df=food_df,
        )
        for issue in day_issues:
            issues.append(f"[{day.title()}] {issue}")

        # Calculate exact day calories
        day_cal = 0.0
        day_items_list: list[str] = []
        for _, item in _iter_meal_items(day_meals):
            fname = str(item.get("food_name", "")).strip()
            qty = _coerce_quantity(item.get("quantity_g", 0.0))
            day_items_list.append(fname)
            food_cal = name_to_cal.get(fname.lower())
            if food_cal is not None and qty > 0:
                day_cal += (food_cal * qty) / 100.0

        daily_calories[day.title()] = round(day_cal, 1)

        # Check daily calorie deviation (±15%)
        dev_pct, within_thresh = check_calorie_deviation(day_cal, calorie_target)
        if not within_thresh:
            issues.append(
                f"[{day.title()}] Calorie deviation of {dev_pct:+.1f}% exceeds ±{int(CALORIE_DEVIATION_THRESHOLD * 100)}% "
                f"(planned: {day_cal:.0f} kcal, target: {calorie_target:.0f} kcal)."
            )

        day_signatures.append(",".join(sorted(day_items_list)))

    # Check weekly variety: avoid having 2 days with exactly the same meals
    if len(day_signatures) >= 7:
        unique_signatures = set(day_signatures)
        if len(unique_signatures) < 4:
            issues.append("Weekly plan lacks sufficient meal variety: multiple days repeat identical foods.")

    # Calculate weekly average calorie deviation
    if daily_calories:
        avg_cal = sum(daily_calories.values()) / len(daily_calories)
        avg_dev_pct, _ = check_calorie_deviation(avg_cal, calorie_target)
    else:
        avg_dev_pct = 0.0

    return issues, avg_dev_pct, daily_calories


def check_macronutrient_compliance(
    planned_calories: float,
    planned_protein: float,
    planned_carbs: float,
    planned_fats: float,
    calorie_target: float,
    protein_target: float,
    carbs_target: float,
    fats_target: float,
    allergies: Optional[list[str]] = None,
    diet_type: str = "veg",
) -> tuple[list[str], dict[str, Any]]:
    """Deterministically evaluate planned macronutrients against targets with realistic tolerances.

    Tolerances:
    - Calories: +/- 15%
    - Protein: -15% to +25% (surplus protein is acceptable for satiety/repair; deficit >15% is flagged)
    - Carbs: +/- 25%
    - Fat: +/- 25% (with contextual limitation notice if severe allergies like dairy+nuts limit dietary fats)
    """
    issues: list[str] = []

    cal_dev = ((planned_calories - calorie_target) / max(calorie_target, 1.0)) * 100.0 if calorie_target > 0 else 0.0
    prot_dev = ((planned_protein - protein_target) / max(protein_target, 1.0)) * 100.0 if protein_target > 0 else 0.0
    carb_dev = ((planned_carbs - carbs_target) / max(carbs_target, 1.0)) * 100.0 if carbs_target > 0 else 0.0
    fat_dev = ((planned_fats - fats_target) / max(fats_target, 1.0)) * 100.0 if fats_target > 0 else 0.0

    # Calorie check
    if abs(cal_dev) > 15.0:
        issues.append(
            f"Calories deviate by {cal_dev:+.1f}% (planned: {planned_calories:.0f} kcal, target: {calorie_target:.0f} kcal)."
        )

    # Protein check
    if prot_dev < -15.0:
        issues.append(
            f"Protein is below target by {abs(prot_dev):.1f}% (planned: {planned_protein:.1f}g, target: {protein_target:.1f}g)."
        )

    # Carbohydrate check
    if abs(carb_dev) > 25.0:
        issues.append(
            f"Carbohydrates deviate by {carb_dev:+.1f}% (planned: {planned_carbs:.1f}g, target: {carbs_target:.1f}g)."
        )

    # Fat check with restriction context
    allergies_set = set(allergies or [])
    has_fat_restriction = bool({"dairy", "tree_nuts", "peanuts"} & allergies_set) and diet_type == "veg"

    limitation_note = None
    if fat_dev < -25.0:
        if has_fat_restriction:
            limitation_note = (
                f"Dietary Limitation Note: Planned fat ({planned_fats:.1f}g) is below theoretical target ({fats_target:.1f}g) "
                f"because major Indian vegetarian fat sources ({', '.join(sorted(allergies_set & {'dairy', 'tree_nuts', 'peanuts'}))}) "
                f"are strictly excluded. Remaining caloric energy is fulfilled by complex carbohydrates and plant protein."
            )
        else:
            issues.append(
                f"Fat is below target by {abs(fat_dev):.1f}% (planned: {planned_fats:.1f}g, target: {fats_target:.1f}g)."
            )
    elif fat_dev > 25.0:
        issues.append(
            f"Fat exceeds target by {fat_dev:+.1f}% (planned: {planned_fats:.1f}g, target: {fats_target:.1f}g)."
        )

    metrics = {
        "calorie_dev_pct": round(cal_dev, 1),
        "protein_dev_pct": round(prot_dev, 1),
        "carb_dev_pct": round(carb_dev, 1),
        "fat_dev_pct": round(fat_dev, 1),
        "limitation_note": limitation_note,
        "is_macro_compliant": len(issues) == 0,
    }

    return issues, metrics


