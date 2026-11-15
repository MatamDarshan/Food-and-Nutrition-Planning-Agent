"""
tools/nutrition_tools.py
------------------------
Tool 1 — calculate_nutrition_targets

LangChain @tool that wraps the core calculation engine.
Accepts flat user-profile fields so the LLM can call it with simple JSON.
Returns a JSON string the agent can read and relay to the user.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from core.user_profile import UserProfile
from core.calculations import calculate_nutrition_targets as _calc_targets


@tool
def calculate_nutrition_targets(
    name: str,
    age: int,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    fitness_goal: str,
    diet_type: str,
    allergies: list[str],
    excluded_foods: list[str],
) -> str:
    """Calculate personalised daily nutritional targets for a user.

    Uses the Mifflin-St Jeor equation for BMR, multiplies by a Physical
    Activity Level factor to get TDEE, then adjusts for fitness goal.
    Macro targets (protein, fat, carbohydrates, fibre) are derived from
    the adjusted calorie target and body weight.

    Args:
        name: User's name.
        age: Age in years (10–100).
        gender: 'male' or 'female'.
        height_cm: Height in centimetres (e.g. 170).
        weight_kg: Body weight in kilograms (e.g. 70).
        activity_level: One of — sedentary | lightly_active |
            moderately_active | very_active | extra_active.
        fitness_goal: One of — weight_loss | maintenance | muscle_gain.
        diet_type: 'veg' or 'non-veg'.
        allergies: List of allergen tags the user must avoid, e.g.
            ['dairy', 'gluten']. Use an empty list if none.
        excluded_foods: List of food names to exclude from the plan.
            Use an empty list if none.

    Returns:
        JSON string containing:
            bmi, bmi_category, bmr, tdee, calorie_target,
            protein_g, carbs_g, fats_g, fiber_g.
        On error, returns a JSON object with an 'error' key.
    """
    try:
        profile = UserProfile(
            name=name,
            age=age,
            gender=gender,
            height_cm=height_cm,
            weight_kg=weight_kg,
            activity_level=activity_level,
            fitness_goal=fitness_goal,
            diet_type=diet_type,
            allergies=allergies,
            excluded_foods=excluded_foods,
        )
        targets = _calc_targets(profile)
        return json.dumps(targets.model_dump(), indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
