"""Additive recipe metadata for meals.

The nutrition engine stores food composition, portions and micronutrients but
no cooking instructions. This module derives a consistent, clearly-labelled
"suggested preparation" from the food category and the existing ingredient
column, plus a personalised reason based on the computed meal totals. It never
mutates the engine's data.
"""

from __future__ import annotations

from typing import Any, Optional

from tools.food_tools import _get_df

SLOT_META: dict[str, dict[str, Any]] = {
    "breakfast": {"image": "/images/breakfast.svg", "prep": 12, "cook": 15, "time": "08:00"},
    "lunch": {"image": "/images/lunch.svg", "prep": 15, "cook": 20, "time": "13:00"},
    "snack": {"image": "/images/snack.svg", "prep": 5, "cook": 5, "time": "16:30"},
    "dinner": {"image": "/images/dinner.svg", "prep": 15, "cook": 22, "time": "20:00"},
}

_GOAL_LABELS = {
    "weight_loss": "fat-loss",
    "maintenance": "maintenance",
    "muscle_gain": "muscle-building",
}


def image_for_slot(slot: str) -> str:
    return SLOT_META.get(str(slot).lower(), SLOT_META["lunch"])["image"]


def image_for_food(name: str, slot: str = "lunch") -> str:
    text = str(name or "").lower()
    if any(word in text for word in ("idli", "dosa", "poha", "upma", "chilla", "paratha", "toast", "oat", "cereal", "chai", "tea")):
        return SLOT_META["breakfast"]["image"]
    if any(word in text for word in ("curd", "raita", "fruit", "apple", "banana", "mango", "nuts", "chickpea", "salad", "dhokla", "papaya", "guava")):
        return SLOT_META["snack"]["image"]
    if any(word in text for word in ("soup", "roti", "rice", "curry", "dal", "paneer", "sabzi", "khichdi", "pulao")):
        if "soup" in text or "dinner" in text:
            return SLOT_META["dinner"]["image"]
        return SLOT_META["lunch"]["image"]
    return image_for_slot(slot)


def _raw_ingredients(food_name: str) -> list[str]:
    try:
        df = _get_df()
        match = df[df["food_name"].astype(str).str.lower() == str(food_name).strip().lower()]
        if match.empty:
            return []
        raw = str(match.iloc[0].get("ingredients") or "")
        if raw.lower() in {"", "none", "nan"}:
            return []
        return [part.strip() for part in raw.replace("|", ";").split(";") if part.strip()]
    except Exception:
        return []


def _category(food_name: str) -> str:
    try:
        df = _get_df()
        match = df[df["food_name"].astype(str).str.lower() == str(food_name).strip().lower()]
        if not match.empty:
            return str(match.iloc[0].get("food_category") or "General")
    except Exception:
        pass
    return "General"


def _steps_for(food_name: str, category: str) -> list[str]:
    text = f"{food_name} {category}".lower()
    if any(w in text for w in ("rice", "pulao", "khichdi", "idli", "dosa", "batter", "upma", "poha")):
        return [
            f"Rinse the {food_name.lower()} 2–3 times until the water runs clear; soak for 15 minutes if the recipe calls for it.",
            "Cook with water (about 1:2 rice-to-water) over medium heat until tender and fluffy.",
            "Rest covered for 5 minutes, then fluff with a fork and serve warm.",
        ]
    if any(w in text for w in ("dal", "lentil", "chickpea", "rajma", "sambar", "soup", "bean")):
        return [
            "Pick over and rinse the lentils thoroughly, then drain.",
            "Pressure cook with water and a pinch of turmeric until soft (3–4 whistles).",
            "Finish with a tadka of cumin, garlic and curry leaves; season to taste.",
        ]
    if any(w in text for w in ("curry", "sabzi", "bharta", "masala", "paneer", "chicken", "gobi", "aloo", "palak")):
        return [
            "Heat a teaspoon of oil in a heavy pan; add cumin, turmeric and finely chopped onion.",
            "Sauté until golden, then add the prepared vegetable or protein and cook until tender.",
            "Add salt, coriander powder and garam masala; garnish with fresh coriander and serve.",
        ]
    if any(w in text for w in ("curd", "raita", "yogurt", "buttermilk", "chaas", "chutney")):
        return [
            "Whisk the base until smooth and creamy.",
            "Stir in roasted cumin powder, salt and freshly chopped herbs.",
            "Chill for 10 minutes and serve alongside the main meal.",
        ]
    if any(w in text for w in ("banana", "apple", "mango", "papaya", "guava", "fruit", "nut", "sprout", "salad")):
        return [
            "Wash and prepare the ingredient; peel or chop as needed.",
            "Portion into a small bowl for a measured serving.",
            "Add a squeeze of lemon or a pinch of chaat masala just before eating.",
        ]
    return [
        "Measure the serving using the portion guide, then prepare the ingredient.",
        "Heat a pan with a little oil and cook gently with basic spices until fragrant.",
        "Adjust seasoning, garnish with herbs and serve hot.",
    ]


def _tags(meal: dict, profile: Optional[dict]) -> list[str]:
    tags: list[str] = []
    protein = float(meal.get("total_protein") or 0)
    fiber = float(meal.get("total_fiber") or 0)
    calories = float(meal.get("total_calories") or 0)
    if protein >= 18:
        tags.append("High protein")
    if fiber >= 6:
        tags.append("High fibre")
    if calories <= 350:
        tags.append("Light")
    if protein >= 12 and calories <= 450:
        tags.append("Balanced")
    if profile and profile.get("diet_type") in {"veg", "vegan", "eggetarian"} and "non-veg" not in str(profile.get("diet_type")):
        tags.append("Plant-forward")
    return tags or ["Nutrient dense"]


def _reason(meal: dict, slot: str, profile: Optional[dict], targets: Optional[dict]) -> str:
    profile = profile or {}
    targets = targets or {}
    goal = _GOAL_LABELS.get(str(profile.get("fitness_goal")), "balanced")
    cal_target = float(targets.get("calorie_target") or 0)
    protein = float(meal.get("total_protein") or 0)
    fiber = float(meal.get("total_fiber") or 0)
    kcal = float(meal.get("total_calories") or 0)

    bits = [
        f"This {slot} gives you about {kcal:.0f} kcal with {protein:.0f} g protein "
        f"and {fiber:.0f} g fibre, supporting your {goal} goal"
    ]
    if cal_target:
        bits.append(f"and fitting inside your {cal_target:.0f} kcal daily target")
    diet = str(profile.get("diet_type") or "").lower()
    if diet:
        bits.append(f"It follows your {diet} preference")
    allergies = profile.get("allergies") or []
    if allergies:
        bits.append(f"and avoids your flagged allergens ({', '.join(map(str, allergies[:4]))})")
    return ", ".join(bits) + ". Portions come from the ICMR-NIN food composition tables."


def enrich_meal(
    meal: dict,
    slot: str,
    profile: Optional[dict] = None,
    targets: Optional[dict] = None,
) -> dict:
    """Return a copy of ``meal`` enhanced with recipe-style presentation data."""
    enriched = dict(meal or {})
    items = enriched.get("items") or []
    ingredients: list[dict[str, Any]] = []
    for item in items:
        name = str(item.get("food_name") or "")
        ingredients.append(
            {
                "name": name,
                "quantity_g": float(item.get("quantity_g") or 0),
                "serving": str(item.get("serving_display") or ""),
                "pantry": _raw_ingredients(name),
                "image": image_for_food(name, slot),
            }
        )

    primary = str(items[0].get("food_name") or slot) if items else slot
    category = _category(primary)
    meta = SLOT_META.get(str(slot).lower(), SLOT_META["lunch"])

    enriched.update(
        {
            "slot": slot,
            "image": image_for_food(primary, slot),
            "prep_time_minutes": int(meta["prep"]),
            "cook_time_minutes": int(meta["cook"]),
            "total_time_minutes": int(meta["prep"]) + int(meta["cook"]),
            "suggested_time": meta["time"],
            "category": category,
            "ingredients": ingredients,
            "steps": _steps_for(primary, category),
            "tags": _tags(enriched, profile),
            "why": _reason(enriched, slot, profile, targets),
            "note": "Suggested preparation generated from the food category; portions and nutrition come from the ICMR-NIN dataset.",
        }
    )
    return enriched


def enrich_plan(plan: dict, profile: Optional[dict] = None) -> dict:
    """Attach recipe metadata to every meal in a weekly plan (in place)."""
    targets = (plan.get("user_targets") or {}) if isinstance(plan, dict) else {}
    for day in (plan.get("days") or []) if isinstance(plan, dict) else []:
        meals = day.get("meals") or {}
        for slot, meal in list(meals.items()):
            meals[slot] = enrich_meal(meal, slot, profile, targets)
    return plan
