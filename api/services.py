"""Service layer that adapts the existing nutrition engine to REST.

Nothing in ``core/``, ``tools/``, ``rag/`` or ``agent/`` is rewritten here: we
only call their public functions and shape the results for the React client.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any, Optional

from core.calculations import (
    DAYS_OF_WEEK,
    build_day_plan_detail,
    calculate_nutrition_targets,
    calculate_weekly_averages,
)
from core.schemas import NutritionTargets, ValidationResult, WeeklyPlan
from core.user_profile import UserProfile
from data.micronutrient_data import (
    RDA_POPULATION,
    RDA_REFERENCE,
    RDA_SOURCE,
)
from tools.food_tools import _get_df, find_food_substitutes

from api.recipes import enrich_plan, image_for_food

# Optional Gemini chat is opt-in; the default path is deterministic + RAG.
USE_GEMINI_CHAT = os.getenv("API_USE_GEMINI_CHAT", "").lower() in {"1", "true", "yes"}

SLOTS = ("breakfast", "lunch", "snack", "dinner")

_FOCUS_FOODS: dict[str, list[str]] = {
    "iron_mg": ["Palak", "Urad dal", "Chickpeas", "Jaggery"],
    "calcium_mg": ["Curd", "Paneer", "Ragi", "Sesame seeds"],
    "zinc_mg": ["Pumpkin seeds", "Chickpeas", "Paneer", "Oats"],
    "vitamin_a_mcg": ["Carrot", "Palak", "Mango", "Pumpkin"],
    "vitamin_b12_mcg": ["Curd", "Paneer", "Eggs", "Fortified cereal"],
    "vitamin_c_mg": ["Amla", "Guava", "Lemon", "Capsicum"],
    "vitamin_d_mcg": ["Fortified milk", "Eggs", "Mushrooms", "Sunlight"],
    "vitamin_b9_mcg": ["Palak", "Lentils", "Chickpeas", "Broccoli"],
}


# ── Profile / targets ─────────────────────────────────────────────────────────

def engine_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Map the extended frontend diet enum onto the engine's two core diets."""
    diet = str(profile.get("diet_type", "veg")).lower()
    allergies = [str(a) for a in (profile.get("allergies") or [])]
    if diet == "vegan" and "dairy" not in allergies:
        allergies.append("dairy")
    if diet == "vegan" and "eggs" not in allergies:
        allergies.append("eggs")
    core_diet = "non-veg" if diet == "non-veg" else "veg"
    return {
        "name": str(profile.get("name") or "User"),
        "age": int(profile["age"]),
        "gender": profile["gender"],
        "height_cm": float(profile["height_cm"]),
        "weight_kg": float(profile["weight_kg"]),
        "activity_level": profile["activity_level"],
        "fitness_goal": profile["fitness_goal"],
        "diet_type": core_diet,
        "allergies": allergies,
        "excluded_foods": [str(f) for f in (profile.get("disliked_foods") or [])],
        "health_conditions": list(profile.get("health_conditions") or []),
        "extended_diet": diet,
    }


def targets_for(profile: dict[str, Any]) -> dict[str, Any]:
    validated = UserProfile(**{k: v for k, v in profile.items() if k != "extended_diet"})
    return calculate_nutrition_targets(validated).model_dump()


def _graph():
    """Import the LangGraph module lazily (keeps API startup fast)."""
    from agent import graph  # type: ignore

    return graph


# ── Weekly plan construction ──────────────────────────────────────────────────

def _normalise_days(raw_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    days: dict[str, dict[str, Any]] = {}
    lowered = {str(k).strip().lower(): v for k, v in (raw_plan or {}).items()}
    for day in DAYS_OF_WEEK:
        value = lowered.get(day.lower())
        if isinstance(value, dict):
            days[day] = value
    if not days and any(slot in lowered for slot in SLOTS):
        days[DAYS_OF_WEEK[0]] = {slot: lowered.get(slot, []) for slot in SLOTS}
    return days


def build_weekly(raw_plan: dict[str, Any], targets: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Turn the engine's raw 7-day JSON into a structured WeeklyPlan dict."""
    targets_obj = NutritionTargets(**targets)
    df = _get_df()
    day_map = _normalise_days(raw_plan)

    day_objects = []
    for day_name in DAYS_OF_WEEK:
        meals = day_map.get(day_name) or {
            slot: (day_map.get(DAYS_OF_WEEK[0], {}).get(slot) or []) for slot in SLOTS
        }
        day_objects.append(
            build_day_plan_detail(
                day_name, meals, df, target_calories=targets_obj.calorie_target
            )
        )
    averages = calculate_weekly_averages(day_objects, targets_obj)
    days = [day.model_dump() for day in day_objects]
    validation_result = None
    try:
        from core.validation import run_weekly_checks

        issues, deviation, _ = run_weekly_checks(
            raw_plan,
            str(profile.get("diet_type", "veg")),
            list(profile.get("allergies") or []),
            list(profile.get("excluded_foods") or []),
            float(targets["calorie_target"]),
            df,
        )
        validation_result = ValidationResult(
            is_valid=not issues,
            issues=issues[:8],
            calorie_deviation_pct=round(deviation, 1),
            planned_calories=averages.avg_calories,
            planned_protein=averages.avg_protein,
            planned_carbs=averages.avg_carbs,
            planned_fats=averages.avg_fat,
            target_calories=targets_obj.calorie_target,
            target_protein=targets_obj.protein_g,
            target_carbs=targets_obj.carbs_g,
            target_fats=targets_obj.fats_g,
        ).model_dump()
    except Exception:
        # Validation is advisory for the UI; plan generation must not fail.
        pass

    plan = WeeklyPlan(
        user_targets=targets_obj,
        days=days,
        weekly_averages=averages.model_dump(),
        rationale=(
            f"A 7-day Indian meal plan built for {profile.get('name', 'you')} using "
            f"ICMR-NIN food composition data and your {profile.get('fitness_goal', 'health')} goal."
        ),
        validation_result=validation_result,
        source_references=[
            "ICMR-NIN RDA 2020",
            "Indian Food Composition Tables (IFCT 2017)",
            RDA_SOURCE,
        ],
    ).model_dump()
    return enrich_plan(plan, profile)


def generate_plan(profile: dict[str, Any], targets: dict[str, Any], mode: str = "fast") -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(presentation_plan, raw_engine_plan)``."""
    graph = _graph()
    if mode == "ai" and _has_gemini_key():
        try:
            from langchain_core.messages import HumanMessage
            import uuid

            result = graph.app_graph.invoke(
                {
                    "user_profile": profile,
                    "nutrition_targets": targets,
                    "messages": [HumanMessage(content="Generate my personalised 7-day meal plan.")],
                    "revision_count": 0,
                },
                config={"configurable": {"thread_id": uuid.uuid4().hex}},
            )
            weekly = result.get("weekly_plan")
            raw = result.get("meal_plan") or {}
            if weekly and _normalise_days(raw):
                return enrich_plan(weekly, profile), raw
        except Exception:
            pass  # Deterministic planner below is the reliable fallback.

    text = graph.generate_demo_meal_plan(profile, targets)
    raw = graph.extract_meal_plan_json(text) or {}
    if not _normalise_days(raw):
        raise ValueError("The meal planner could not produce a valid 7-day plan. Please try again.")
    return build_weekly(raw, targets, profile), raw


def _has_gemini_key() -> bool:
    try:
        from config.settings import settings

        return bool(settings.google_api_key)
    except Exception:
        return False


def regenerate_meal(
    record: dict[str, Any], day: str, slot: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Regenerate one meal only, leaving the rest of the week untouched."""
    profile = record["profile"]
    targets = record["targets"]
    raw = json.loads(json.dumps(record["raw_plan"]))
    day_map = _normalise_days(raw)
    day_name = next((d for d in DAYS_OF_WEEK if d.lower() == str(day).lower()), DAYS_OF_WEEK[0])
    current = list((day_map.get(day_name, {}).get(slot) or []))
    current_names = {str(item.get("food_name", "")).lower() for item in current}

    # Ask the engine for an alternative plan with this meal's current foods excluded.
    excluded = list(profile.get("excluded_foods") or []) + list(current_names)
    attempt_profile = {**profile, "excluded_foods": excluded}
    graph = _graph()
    for _ in range(3):
        try:
            text = graph.generate_demo_meal_plan(attempt_profile, targets)
            candidate_raw = graph.extract_meal_plan_json(text) or {}
            candidate_map = _normalise_days(candidate_raw)
            replacement = candidate_map.get(day_name, {}).get(slot) or []
            replacement_names = {str(i.get("food_name", "")).lower() for i in replacement}
            if replacement and not replacement_names & current_names:
                day_map.setdefault(day_name, {})[slot] = replacement
                raw[day_name] = day_map[day_name]
                return build_weekly(raw, targets, profile), raw
        except Exception:
            break
        excluded.extend(replacement_names)
        attempt_profile = {**profile, "excluded_foods": excluded}

    raise ValueError("No alternative could be generated for this meal. Try swapping a food instead.")


def swap_food(record: dict[str, Any], day: str, slot: str, food_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Replace the first item of a meal with an engine-approved substitute."""
    profile = record["profile"]
    targets = record["targets"]
    raw = json.loads(json.dumps(record["raw_plan"]))
    day_map = _normalise_days(raw)
    day_name = next((d for d in DAYS_OF_WEEK if d.lower() == str(day).lower()), DAYS_OF_WEEK[0])
    items = list(day_map.get(day_name, {}).get(slot) or [])
    if not items:
        raise ValueError("That meal is empty and cannot be swapped.")
    old = items[0]
    df = _get_df()
    match = df[df["food_name"].astype(str).str.lower() == str(food_name).strip().lower()]
    if match.empty:
        raise ValueError(f"'{food_name}' is not in the nutrition database.")
    row = match.iloc[0]
    old_calories = float(row.get("calories") or 0)
    previous_calories = float(
        df.loc[df["food_name"].astype(str).str.lower() == str(old.get("food_name", "")).lower(), "calories"].iloc[0]
    ) if not df.loc[df["food_name"].astype(str).str.lower() == str(old.get("food_name", "")).lower()].empty else float(old.get("quantity_g") or 100)
    quantity = 100.0
    if previous_calories > 0:
        quantity = max(20.0, min(400.0, float(old.get("quantity_g") or 100) * previous_calories / old_calories))
    items[0] = {"food_name": str(row["food_name"]), "quantity_g": round(quantity, 1)}
    day_map.setdefault(day_name, {})[slot] = items
    raw[day_name] = day_map[day_name]
    return build_weekly(raw, targets, profile), raw


# ── Foods / substitutes ───────────────────────────────────────────────────────

def search_foods(
    query: str = "",
    diet: str = "all",
    meal: str = "",
    category: str = "",
    limit: int = 24,
) -> list[dict[str, Any]]:
    df = _get_df()
    mask = df["food_name"].astype(str).str.contains(re.escape(query), case=False, regex=True, na=False) if query else True
    if str(diet).lower() == "veg":
        mask = mask & (df["diet_type"].astype(str).str.lower() == "veg")
    if meal:
        mask = mask & df["meal_type"].astype(str).str.contains(meal, case=False, regex=False, na=False)
    if category:
        mask = mask & df["food_category"].astype(str).str.contains(category, case=False, regex=False, na=False)
    rows = df[mask].head(max(1, min(limit, 60)))
    result: list[dict[str, Any]] = []
    for _, row in rows.iterrows():
        try:
            glycemic = float(row.get("glycemic_index"))
            if math.isnan(glycemic):
                glycemic = None
        except (TypeError, ValueError):
            glycemic = None
        result.append(
            {
                "food_id": int(row["food_id"]),
                "food_name": str(row["food_name"]),
                "calories": float(row["calories"]),
                "protein": float(row["protein"]),
                "carbohydrates": float(row["carbohydrates"]),
                "fats": float(row["fats"]),
                "fiber": float(row["fiber"]),
                "diet_type": str(row["diet_type"]),
                "meal_type": str(row["meal_type"]),
                "food_category": str(row["food_category"]),
                "ingredients": str(row.get("ingredients") or ""),
                "allergens": str(row.get("allergens") or "none"),
                "glycemic_index": glycemic,
                "image": image_for_food(str(row["food_name"]), str(row["meal_type"])),
                "prep_time_minutes": 15,
            }
        )
    return result


def substitutes(food_name: str, profile: Optional[dict[str, Any]] = None, meal: str = "") -> list[dict[str, Any]]:
    profile = profile or {}
    payload = {
        "food_name": food_name,
        "diet_type": str(profile.get("diet_type", "veg")),
        "meal_type": meal,
        "allergies": list(profile.get("allergies") or []),
        "top_n": 5,
        "excluded_foods": list(profile.get("disliked_foods") or []),
    }
    try:
        result = json.loads(find_food_substitutes.invoke(payload))
    except Exception:
        result = {}
    items = []
    for sub in result.get("substitutes") or []:
        items.append(
            {
                "food_name": str(sub.get("food_name")),
                "calories": float(sub.get("calories") or 0),
                "protein": float(sub.get("protein") or 0),
                "similarity_score": float(sub.get("similarity_score") or 0),
                "image": image_for_food(str(sub.get("food_name")), meal),
                "reason": f"Similar macro profile ({float(sub.get('similarity_score') or 0):.2f} match) and compliant with your diet.",
            }
        )
    return items


# ── Grocery / insights / export ───────────────────────────────────────────────

def grocery_list(plan: dict[str, Any]) -> list[dict[str, Any]]:
    collected: dict[str, dict[str, Any]] = {}
    for day in plan.get("days") or []:
        day_name = str(day.get("day_name") or "")
        for meal in (day.get("meals") or {}).values():
            for ingredient in meal.get("ingredients") or []:
                name = str(ingredient.get("name") or "").strip()
                if not name:
                    continue
                key = name.lower()
                entry = collected.setdefault(
                    key,
                    {
                        "name": name,
                        "total_grams": 0.0,
                        "serving": str(ingredient.get("serving") or ""),
                        "category": str(meal.get("category") or "General"),
                        "days": [],
                        "image": str(ingredient.get("image") or ""),
                    },
                )
                entry["total_grams"] += float(ingredient.get("quantity_g") or 0)
                if day_name not in entry["days"]:
                    entry["days"].append(day_name)
    for entry in collected.values():
        entry["total_grams"] = round(entry["total_grams"], 1)
    return sorted(collected.values(), key=lambda item: item["name"].lower())


def insights(plan: dict[str, Any]) -> dict[str, Any]:
    targets = plan.get("user_targets") or {}
    days = plan.get("days") or []
    averages = plan.get("weekly_averages") or {}

    macros = [
        {
            "key": "protein_g",
            "label": "Protein",
            "unit": "g",
            "average": round(float(averages.get("avg_protein") or 0), 1),
            "target": round(float(targets.get("protein_g") or 0), 1),
        },
        {
            "key": "carbs_g",
            "label": "Carbohydrates",
            "unit": "g",
            "average": round(float(averages.get("avg_carbs") or 0), 1),
            "target": round(float(targets.get("carbs_g") or 0), 1),
        },
        {
            "key": "fats_g",
            "label": "Fats",
            "unit": "g",
            "average": round(float(averages.get("avg_fat") or 0), 1),
            "target": round(float(targets.get("fats_g") or 0), 1),
        },
        {
            "key": "fiber_g",
            "label": "Fibre",
            "unit": "g",
            "average": round(float(averages.get("avg_fiber") or 0), 1),
            "target": round(float(targets.get("fiber_g") or 0), 1),
        },
    ]

    micronutrients: list[dict[str, Any]] = []
    for key, meta in RDA_REFERENCE.items():
        values = [float((day.get("micronutrients") or {}).get(key) or 0) for day in days]
        average = sum(values) / len(values) if values else 0.0
        target = float(meta.get("target") or 0)
        pct = round((average / target) * 100, 1) if target else 0.0
        micronutrients.append(
            {
                "key": key,
                "label": str(meta.get("label") or key),
                "unit": str(meta.get("unit") or ""),
                "category": str(meta.get("category") or "Other"),
                "average": round(average, 2),
                "target": target,
                "percent": min(pct, 200.0),
                "status": "low" if pct < 70 else "good" if pct <= 130 else "high",
                "foods": _FOCUS_FOODS.get(key, []),
            }
        )

    trend = [
        {
            "day": str(day.get("day_name"))[:3],
            "calories": round(float(day.get("total_calories") or 0), 1),
            "protein": round(float(day.get("total_protein") or 0), 1),
            "carbs": round(float(day.get("total_carbs") or 0), 1),
            "fats": round(float(day.get("total_fat") or 0), 1),
        }
        for day in days
    ]
    focus = sorted(
        [n for n in micronutrients if n["status"] == "low"],
        key=lambda n: n["percent"],
    )[:5]

    return {
        "macros": macros,
        "micronutrients": micronutrients,
        "trend": trend,
        "focus": focus,
        "targets": {
            "calories": round(float(targets.get("calorie_target") or 0), 1),
            "protein": round(float(targets.get("protein_g") or 0), 1),
            "carbs": round(float(targets.get("carbs_g") or 0), 1),
            "fats": round(float(targets.get("fats_g") or 0), 1),
            "fiber": round(float(targets.get("fiber_g") or 0), 1),
        },
        "rda_population": RDA_POPULATION,
        "rda_source": RDA_SOURCE,
        "validation": plan.get("validation_result"),
    }


def export_plan(plan: dict[str, Any], profile: dict[str, Any]) -> bytes:
    """Render the 7-day plan as a downloadable PDF."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="NutriPlan 7-Day Nutrition Plan",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="NPTitle", parent=styles["Title"], fontSize=22, leading=26, textColor=colors.HexColor("#14532d"), spaceAfter=8))
    styles.add(ParagraphStyle(name="NPSub", parent=styles["Normal"], fontSize=10, leading=14, textColor=colors.HexColor("#475569"), spaceAfter=12))
    styles.add(ParagraphStyle(name="NPDay", parent=styles["Heading2"], fontSize=14, leading=18, textColor=colors.HexColor("#166534"), spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="NPMeal", parent=styles["Heading3"], fontSize=11, leading=14, textColor=colors.HexColor("#0f172a"), spaceBefore=6, spaceAfter=2))
    styles.add(ParagraphStyle(name="NPBody", parent=styles["Normal"], fontSize=9, leading=12, textColor=colors.HexColor("#334155"), spaceAfter=2))
    styles.add(ParagraphStyle(name="NPSmall", parent=styles["Normal"], fontSize=8, leading=10, textColor=colors.HexColor("#64748b"), spaceAfter=6))

    targets = plan.get("user_targets") or {}
    name = str(profile.get("name") or "My")
    story = [
        Paragraph(f"{name}'s 7-Day Nutrition Plan", styles["NPTitle"]),
        Paragraph(
            f"Daily target: <b>{float(targets.get('calorie_target', 0)):.0f} kcal</b> · "
            f"Protein {float(targets.get('protein_g', 0)):.0f} g · "
            f"Carbs {float(targets.get('carbs_g', 0)):.0f} g · "
            f"Fats {float(targets.get('fats_g', 0)):.0f} g",
            styles["NPSub"],
        ),
        Paragraph(
            "Nutrition information is derived from ICMR-NIN RDA 2020 and IFCT 2017. "
            "Recipe steps are suggested preparation guidance; macros are calculated from IFCT quantities.",
            styles["NPSmall"],
        ),
    ]

    for day in plan.get("days") or []:
        day_name = str(day.get("day_name") or "Day")
        totals = (
            f"{float(day.get('total_calories') or 0):.0f} kcal · "
            f"P {float(day.get('total_protein') or 0):.0f} g · "
            f"C {float(day.get('total_carbs') or 0):.0f} g · "
            f"F {float(day.get('total_fat') or 0):.0f} g"
        )
        story.append(Paragraph(f"{day_name} <font color='#475569' size='9'>— {totals}</font>", styles["NPDay"]))

        for slot, meal in (day.get("meals") or {}).items():
            meal_title = str(slot).replace("_", " ").title()
            story.append(Paragraph(meal_title, styles["NPMeal"]))
            rows = [["Food", "Quantity", "Serving"]]
            for item in meal.get("items") or []:
                rows.append([
                    Paragraph(str(item.get("food_name") or ""), styles["NPBody"]),
                    f"{float(item.get('quantity_g') or 0):.0f} g",
                    str(item.get("serving_display") or ""),
                ])
            table = Table(rows, colWidths=[78 * mm, 28 * mm, 58 * mm], repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ecfdf5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#166534")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(table)
            story.append(Paragraph(
                f"Meal total: {float(meal.get('total_calories') or 0):.0f} kcal · "
                f"{float(meal.get('total_protein') or 0):.0f} g protein · "
                f"{int(meal.get('total_time_minutes') or 20)} min prep",
                styles["NPSmall"],
            ))
        story.append(Spacer(1, 2 * mm))

    doc.build(story)
    return buffer.getvalue()


# ── Chat ──────────────────────────────────────────────────────────────────────

_SUGGESTIONS = [
    "Suggest a high-protein snack",
    "What can I substitute for paneer?",
    "Why was this meal recommended for me?",
    "How can I improve my iron intake?",
    "Explain my calorie target",
]


def _rag_details(message: str) -> list[dict[str, Any]]:
    try:
        from rag.retriever import retrieve_with_details

        details = retrieve_with_details(message, k=3)
        return [d for d in details if d.get("is_relevant")]
    except Exception:
        return []


def _find_food_in_message(message: str, plan: dict[str, Any]) -> str:
    lowered = message.lower()
    known: list[str] = []
    for day in plan.get("days") or []:
        for meal in (day.get("meals") or {}).values():
            for item in meal.get("items") or []:
                name = str(item.get("food_name") or "")
                if name and name.lower() in lowered:
                    known.append(name)
    return max(known, key=len) if known else ""


def chat_reply(
    message: str,
    history: list[dict[str, Any]],
    profile: Optional[dict[str, Any]],
    plan: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Answer with plan context + RAG evidence, avoiding a Gemini call by default."""
    text = message.strip()
    lowered = text.lower()
    profile = profile or {}
    details = _rag_details(text)
    sources = []
    for detail in details[:3]:
        sources.append(
            {
                "source": os.path.basename(str(detail.get("document") or "ICMR-NIN Guideline")),
                "page": int(detail.get("page") or 1),
                "condition": None,
            }
        )

    targets = (plan or {}).get("user_targets") or {}
    cal = float(targets.get("calorie_target") or 0)
    protein = float(targets.get("protein_g") or 0)
    goal = str(profile.get("fitness_goal") or "maintenance").replace("_", " ")

    substitute_words = ("substitute", "swap", "replace", "alternative", "instead of")
    if any(word in lowered for word in substitute_words):
        food = _find_food_in_message(text, plan or {})
        if not food:
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z-]{3,}", text) if w.lower() not in {
                "what", "which", "food", "substitute", "replace", "alternative", "instead", "suggest",
            }]
            food = words[-1] if words else "paneer"
        options = substitutes(food, profile)
        if options:
            names = ", ".join(f"**{o['food_name']}** ({o['calories']:.0f} kcal/100g)" for o in options[:4])
            reply = (
                f"Good question. For **{food}**, the closest compliant options in our food database are: {names}. "
                "I matched them on calories, protein, carbs and fat while respecting your diet and allergen settings. "
                "Open any meal card and tap **Swap Meal** to apply one instantly."
            )
        else:
            reply = (
                f"I couldn't find a close substitute for **{food}** that fits your current diet and allergy filters. "
                "Try removing a disliked food from your profile or ask me for a specific food you'd like included."
            )
    elif any(word in lowered for word in ("why", "recommend", "chosen", "picked")):
        reply = (
            f"Your meals are selected from the ICMR-NIN food table and then checked against your profile: "
            f"{profile.get('diet_type', 'vegetarian')} diet, {goal} goal"
            + (f", allergies ({', '.join(profile.get('allergies', []))})" if profile.get("allergies") else "")
            + f", and a {cal:.0f} kcal daily target with {protein:.0f} g protein. "
            "Each recipe card explains its own calorie and macro contribution — open **Why this meal?** for the exact breakdown."
        )
    elif any(word in lowered for word in ("iron", "anaemia", "anemia")):
        reply = (
            "For iron, pair a vitamin-C source with a legume or leafy vegetable — for example amla or lemon with palak or dal. "
            "Tea and coffee immediately after meals reduce iron absorption, so keep them at least an hour away. "
            "Your weekly planner already repeats iron-rich dals and greens; the Insights page shows your daily average against the ICMR RDA."
        )
    elif any(word in lowered for word in ("protein", "muscle", "weight")):
        reply = (
            f"Your target is about **{protein:.0f} g protein per day** at **{cal:.0f} kcal**, built from your body weight and {goal} goal. "
            "Spread it across all four meals — Indian staples like dal, paneer, curd, chickpeas and sprouts make this easier without supplements. "
            "Check the Insights page for your actual weekly average."
        )
    elif any(word in lowered for word in ("calorie", "target", "bmr", "tdee")):
        reply = (
            f"We estimate your BMR with the Mifflin–St Jeor equation, multiply by your activity level for TDEE, "
            f"then adjust for your {goal} goal. That gives your **{cal:.0f} kcal/day** target. "
            "The plan is checked to keep each day close to that number using the ICMR-NIN food composition tables."
        )
    elif details:
        excerpt = str(details[0].get("text") or "").strip()
        excerpt = re.sub(r"\s+", " ", excerpt)[:480]
        reply = (
            f"Based on the nutrition guidance in our knowledge base: {excerpt}"
            + ("\n\nThis is general guidance — your plan already applies it to your own targets and restrictions." if excerpt else "")
        )
    else:
        reply = (
            f"I'm your AI Nutritionist, tuned to Indian food and your profile. "
            f"You're aiming for {cal:.0f} kcal and {protein:.0f} g protein a day on a {goal} plan. "
            "Ask me about a specific nutrient, a food substitution, or why a meal was recommended — "
            "I'll use your plan and the ICMR-NIN knowledge base to answer."
        )

    if USE_GEMINI_CHAT and _has_gemini_key():
        gemini_reply = _gemini_chat(text, reply, profile, plan, details)
        if gemini_reply:
            reply = gemini_reply

    return {
        "reply": reply,
        "citations": sources,
        "suggestions": _SUGGESTIONS,
    }


def _gemini_chat(
    message: str,
    grounded: str,
    profile: dict[str, Any],
    plan: Optional[dict[str, Any]],
    details: list[dict[str, Any]],
) -> Optional[str]:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from config.settings import settings

        evidence = "\n".join(
            f"- {d.get('document')} p.{d.get('page')}: {str(d.get('text'))[:400]}" for d in details
        )
        llm = ChatGoogleGenerativeAI(
            model=settings.model_name,
            temperature=0.2,
            google_api_key=settings.google_api_key,
        )
        response = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "You are a cautious Indian nutritionist. Use only the provided evidence and profile. "
                        "Answer in under 140 words, cite the evidence when used, and never diagnose."
                    )
                ),
                HumanMessage(
                    content=f"Profile: {profile}\nEvidence: {evidence}\nEngine answer: {grounded}\nQuestion: {message}"
                ),
            ]
        )
        return str(response.content).strip() or None
    except Exception:
        return None
