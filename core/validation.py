"""
core/validation.py
------------------
Pure, side-effect-free validation functions for meal plan rule checking.
No I/O, no network, no global state — only Pandas DataFrame operations.

Called by Tool 5 (validate_meal_plan) and directly by the LangGraph
Meal Validation node.
"""

from __future__ import annotations

import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────
CALORIE_DEVIATION_THRESHOLD = 0.15   # ±15 % of daily calorie target is acceptable
REQUIRED_MEALS = ["breakfast", "lunch", "dinner"]
MACRO_COLS = ["calories", "protein", "carbohydrates", "fats", "fiber"]


# ── Internal helpers ───────────────────────────────────────────────────────────

def _all_items(plan: dict) -> list[dict]:
    """Flatten all meal slots into a single list of food-entry dicts."""
    items: list[dict] = []
    for meal in ["breakfast", "lunch", "snack", "dinner"]:
        items.extend(plan.get(meal, []))
    return items


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
    name_to_diet: dict[str, str] = food_df.set_index("food_name")["diet_type"].to_dict()
    for item in _all_items(plan):
        food_name = item.get("food_name", "")
        item_diet = name_to_diet.get(food_name)
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
    """No food in the plan may contain any of the user's allergens."""
    if not allergies:
        return []
    issues: list[str] = []
    name_to_allergens: dict[str, str] = (
        food_df.set_index("food_name")["allergens"].to_dict()
    )
    for item in _all_items(plan):
        food_name = item.get("food_name", "")
        raw = name_to_allergens.get(food_name, "none")
        # allergens column uses "|" as separator (matches food_data.csv)
        food_allergens = {a.strip().lower() for a in str(raw).replace(";", "|").split("|")}
        for allergen in allergies:
            allergen_lower = allergen.lower()
            if allergen_lower in food_allergens and allergen_lower != "none":
                issues.append(
                    f"'{food_name}' contains '{allergen}' "
                    f"which the user is allergic to."
                )
                break  # one issue per food item, not per allergen
    return issues


def check_excluded_foods(
    plan: dict,
    excluded_foods: list[str],
) -> list[str]:
    """No food name that the user excluded may appear in the plan."""
    if not excluded_foods:
        return []
    excluded_lower = {f.lower() for f in excluded_foods}
    return [
        f"'{item.get('food_name', '')}' is in the user's excluded foods list."
        for item in _all_items(plan)
        if item.get("food_name", "").lower() in excluded_lower
    ]


def check_meal_completeness(plan: dict) -> list[str]:
    """Breakfast, lunch, and dinner must each have at least one food item."""
    return [
        f"Meal plan is missing required meal: '{meal}'."
        for meal in REQUIRED_MEALS
        if not plan.get(meal)
    ]


def check_quantities(plan: dict) -> list[str]:
    """All food quantities must be positive numbers greater than zero."""
    issues: list[str] = []
    for meal, items in plan.items():
        for item in items:
            qty = item.get("quantity_g", 0)
            try:
                qty = float(qty)
            except (TypeError, ValueError):
                qty = 0.0
            if qty <= 0:
                issues.append(
                    f"'{item.get('food_name', 'unknown')}' in {meal} "
                    f"has an invalid quantity: {qty} g."
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
    issues: list[str] = []
    issues += check_meal_completeness(plan)
    issues += check_quantities(plan)
    issues += check_diet_compliance(plan, diet_type, food_df)
    issues += check_allergen_compliance(plan, allergies, food_df)
    issues += check_excluded_foods(plan, excluded_foods)

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
