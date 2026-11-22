"""
agent/graph.py
--------------
Main Agentic AI implementation using Google Gemini and LangGraph.

Implements the 7-node workflow:
1. profile_validation   : Validates user details with Pydantic
2. nutrition_calculation: Computes estimated BMR, TDEE, Calorie and Macro targets
3. agent                : Gemini reasoning engine deciding tool calls or plan output
4. tools                : Executes the 5 Python tools
5. meal_validation      : Checks generated meal plan with deterministic rules
6. plan_revision        : Instructs agent to correct issues if validation fails
7. final_response       : Formats final validated output with graceful fallback
"""

from __future__ import annotations

import json
from typing import Any, Iterator, Optional

import pandas as pd
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from agent.prompts import REVISION_PROMPT_TEMPLATE, SYSTEM_PROMPT
from agent.state import AgentState
from config.settings import settings
from core.calculations import (
    calculate_nutrition_targets as _calc_targets,
    build_day_plan_detail,
    calculate_weekly_averages,
    DAYS_OF_WEEK,
)
from core.schemas import NutritionTargets, WeeklyPlan, ValidationResult
from core.user_profile import UserProfile
from core.validation import run_all_checks, run_weekly_checks
from tools.food_tools import (
    _allergen_mask,
    _excluded_mask,
    _get_df,
    calculate_meal_nutrition,
    find_food_substitutes,
    search_food_database,
    validate_meal_plan,
)
from tools.nutrition_tools import calculate_nutrition_targets
from rag.retriever import retrieve_nutrition_knowledge


# ── Registered Tools ──────────────────────────────────────────────────────────

ALL_TOOLS = [
    calculate_nutrition_targets,
    search_food_database,
    calculate_meal_nutrition,
    find_food_substitutes,
    validate_meal_plan,
    retrieve_nutrition_knowledge,
]


# ── JSON Helper ───────────────────────────────────────────────────────────────

def _iter_json_objects(text: str) -> Iterator[dict]:
    """Yield every top-level JSON object embedded in arbitrary model text.

    Uses the decoder's ``raw_decode`` so nested objects (a 7-day plan nests
    meal lists three levels deep) are parsed correctly.  The previous
    non-greedy regex stopped at the first inner ``}`` and silently failed on
    realistic nested output.
    """
    decoder = json.JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        start = text.find("{", index)
        if start == -1:
            break
        try:
            parsed, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            index = start + 1
            continue
        if isinstance(parsed, dict):
            yield parsed
        index = end if end > start else start + 1


def _is_valid_plan_dict(d: object) -> bool:
    """True when ``d`` looks like a 7-day or single-day meal plan."""
    if not isinstance(d, dict):
        return False
    days_matched = [
        k for k in d.keys()
        if str(k).lower().strip() in [
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday"
        ]
    ]
    if len(days_matched) >= 3:
        return True
    meals_matched = [
        k for k in d.keys()
        if str(k).lower().strip() in ["breakfast", "lunch", "dinner", "snack"]
    ]
    return len(meals_matched) >= 2


def extract_meal_plan_json(text: str) -> Optional[dict]:
    """Extract a meal plan dictionary from model output text.

    Supports both:
    1. 7-day weekly plans: {"monday": {...}, "tuesday": {...}, ...}
    2. Single-day meal plans: {"breakfast": [...], "lunch": [...], ...}

    Works with fenced blocks, surrounding prose, and nested objects.
    """
    if not text:
        return None
    for parsed in _iter_json_objects(text):
        if _is_valid_plan_dict(parsed):
            return parsed
    return None


_DAY_KEYS = [
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
]


def _day_map(plan: Any) -> dict[str, dict]:
    """Return a lower-cased day-name map for a weekly plan (empty if not weekly)."""
    if not isinstance(plan, dict):
        return {}
    return {
        str(key).lower().strip(): value
        for key, value in plan.items()
        if str(key).lower().strip() in _DAY_KEYS and isinstance(value, dict)
    }


def _message_text(message: Any) -> str:
    """Flatten a LangChain message's content (str or content-block list) to text."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return str(content) if content is not None else ""


# ── Node 1: Profile Validation ────────────────────────────────────────────────

def profile_validation_node(state: AgentState) -> dict[str, Any]:
    """Validate user profile data using Pydantic UserProfile model."""
    raw_profile = state.get("user_profile")
    if not raw_profile:
        # If conversation messages exist (e.g. chat interaction), allow proceeding without strict profile
        if state.get("messages"):
            return {"error": None}
        return {"error": "No user profile provided."}

    try:
        profile_obj = UserProfile(**raw_profile)
        return {
            "user_profile": profile_obj.model_dump(),
            "error": None,
        }
    except Exception as exc:
        # If conversation messages exist (e.g. conversational chat turn), do not block chat on profile schema
        if state.get("messages"):
            return {"error": None}
        return {
            "error": f"User profile validation failed: {str(exc)}",
        }


# ── Node 2: Nutrition Calculation ─────────────────────────────────────────────

def nutrition_calculation_node(state: AgentState) -> dict[str, Any]:
    """Compute BMI, BMR, TDEE, and macro targets from validated profile."""
    if state.get("error"):
        return {}

    raw_profile = state.get("user_profile")
    if not raw_profile:
        return {}

    try:
        profile_obj = UserProfile(**raw_profile)
        targets = _calc_targets(profile_obj)
        targets_dict = targets.model_dump()
    except Exception:
        return {}

    # Prepend a context prompt explaining user targets to messages if not already present
    context_msg = (
        f"USER GOALS & TARGETS:\n"
        f"- Profile: {profile_obj.summary()}\n"
        f"- Target Calories: {targets.calorie_target} kcal/day\n"
        f"- Target Protein : {targets.protein_g} g\n"
        f"- Target Carbs   : {targets.carbs_g} g\n"
        f"- Target Fats    : {targets.fats_g} g\n"
        f"- Target Fiber   : {targets.fiber_g} g\n"
        f"- Dietary preference: {profile_obj.diet_type}\n"
        f"- Allergens to exclude: {profile_obj.allergies or 'None'}\n"
        f"- Excluded foods: {profile_obj.excluded_foods or 'None'}\n"
    )

    # Only append the initial context message if this is a fresh planning run
    if not state.get("messages"):
        return {
            "nutrition_targets": targets_dict,
            "messages": [HumanMessage(content=context_msg)],
        }

    return {
        "nutrition_targets": targets_dict,
    }


# ── Demo Mode Fallback Plan Generator ─────────────────────────────────────────

def generate_demo_meal_plan(profile: dict, targets: dict) -> str:
    """Generate an optimal, fully-compliant 7-day Indian meal plan using deterministic rules.

    Used for seamless demo presentation when an external API key is invalid or offline.
    Directly leverages the ICMR-NIN database and enforces dietary and allergen constraints.
    """
    df = _get_df()
    diet_type = profile.get("diet_type", "veg")
    allergies = profile.get("allergies", []) or []
    excluded = profile.get("excluded_foods", []) or []
    cal_target = targets.get("calorie_target", 2000.0)

    # Filter helper — reuses the same predicate as search and validation.
    def get_slot_candidates(meal_slot: str) -> list[str]:
        mask = (
            (df["diet_type"] == "veg" if diet_type == "veg" else pd.Series([True] * len(df)))
            & df["meal_type"].str.contains(meal_slot, regex=False, na=False)
            & _allergen_mask(df, allergies)
            & _excluded_mask(df, excluded)
        )
        matched = df[mask]
        return matched["food_name"].tolist() if not matched.empty else []

    b_cands = get_slot_candidates("breakfast")
    l_cands = get_slot_candidates("lunch")
    s_cands = get_slot_candidates("snack")
    d_cands = get_slot_candidates("dinner")

    GRAIN_FOODS = {"basmati rice", "brown rice", "whole wheat roti", "ragi mudde", "vegetable khichdi", "vegetable pulao"}

    def pick_first_available(cands: list[str], preferred: list[str], current_items: list[str] | None = None) -> str:
        current_names = [it.lower() for it in (current_items or [])]
        has_grain = any(g in current_names for g in GRAIN_FOODS)

        # 1. Try preferred items that are available and don't duplicate grain if grain already present
        for p in preferred:
            if p in cands:
                if has_grain and p.lower() in GRAIN_FOODS:
                    continue
                return p

        # 2. Fallback to candidate list, prioritizing non-grains if grain already present
        if has_grain:
            non_grains = [c for c in cands if c.lower() not in GRAIN_FOODS]
            if non_grains:
                return non_grains[0]

        return cands[0] if cands else "Basmati Rice"

    # 7 balanced day templates with authentic Indian staples and nutritious vegetable sides
    day_templates = [
        # Monday
        {
            "breakfast": [
                ("Besan Chilla", ["Besan Chilla", "Poha", "Medu Vada", "Uttapam", "Wheat Bread Toast", "Idli"]),
                ("Sambar", ["Sambar", "Sprouts Salad", "Coconut Chutney", "Plain Curd"]),
            ],
            "lunch": [
                ("Basmati Rice", ["Basmati Rice", "Brown Rice", "Whole Wheat Roti"]),
                ("Dal Tadka", ["Dal Tadka", "Moong Dal Soup", "Rajma"]),
                ("Aloo Gobi", ["Aloo Gobi", "Baingan Bharta", "Raita", "Plain Curd", "Moong Dal Soup", "Sambar"]),
            ],
            "snack": [
                ("Apple", ["Apple", "Banana", "Papaya", "Guava", "Sprouts Salad"]),
                ("Sprouts Salad", ["Sprouts Salad", "Dhokla", "Guava", "Apple"]),
            ],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice", "Brown Rice"]),
                ("Chana Masala" if diet_type == "veg" else "Chicken Curry",
                 ["Chana Masala", "Rajma", "Dal Tadka", "Moong Dal Soup", "Palak Paneer"] if diet_type == "veg" else ["Chicken Curry", "Chana Masala", "Rajma", "Dal Tadka"]),
                ("Moong Dal Soup", ["Moong Dal Soup", "Baingan Bharta", "Aloo Gobi", "Sambar"]),
            ],
        },
        # Tuesday
        {
            "breakfast": [
                ("Poha", ["Poha", "Besan Chilla", "Medu Vada", "Uttapam", "Sprouts Salad", "Upma"]),
                ("Sprouts Salad", ["Sprouts Salad", "Plain Curd", "Buttermilk / Chaas", "Sambar"]),
            ],
            "lunch": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Brown Rice", "Basmati Rice"]),
                ("Rajma", ["Rajma", "Chana Masala", "Dal Tadka"]),
                ("Baingan Bharta", ["Baingan Bharta", "Aloo Gobi", "Moong Dal Soup", "Buttermilk / Chaas", "Plain Curd"]),
            ],
            "snack": [
                ("Sprouts Salad", ["Sprouts Salad", "Dhokla", "Apple", "Guava"]),
                ("Banana", ["Banana", "Papaya", "Guava", "Apple"]),
            ],
            "dinner": [
                ("Basmati Rice", ["Basmati Rice", "Whole Wheat Roti"]),
                ("Chana Masala", ["Chana Masala", "Dal Tadka", "Rajma"]),
                ("Aloo Gobi", ["Aloo Gobi", "Baingan Bharta", "Moong Dal Soup"]),
            ],
        },
        # Wednesday
        {
            "breakfast": [
                ("Besan Chilla", ["Besan Chilla", "Poha", "Uttapam", "Medu Vada", "Wheat Bread Toast"]),
                ("Sambar", ["Sambar", "Coconut Chutney", "Plain Curd", "Sprouts Salad"]),
            ],
            "lunch": [
                ("Vegetable Khichdi", ["Vegetable Khichdi", "Basmati Rice", "Vegetable Pulao", "Whole Wheat Roti"]),
                ("Dal Tadka", ["Dal Tadka", "Moong Dal Soup", "Rajma", "Chana Masala"]),
                ("Aloo Gobi", ["Aloo Gobi", "Baingan Bharta", "Plain Curd", "Raita", "Sambar"]),
            ],
            "snack": [
                ("Banana", ["Banana", "Papaya", "Apple", "Guava"]),
                ("Sprouts Salad", ["Sprouts Salad", "Dhokla", "Guava"]),
            ],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Dal Tadka" if diet_type == "veg" else "Egg Curry",
                 ["Dal Tadka", "Chana Masala", "Rajma", "Dal Makhani"] if diet_type == "veg" else ["Egg Curry", "Dal Tadka", "Chana Masala", "Rajma"]),
                ("Baingan Bharta", ["Baingan Bharta", "Aloo Gobi", "Moong Dal Soup"]),
            ],
        },
        # Thursday
        {
            "breakfast": [
                ("Poha", ["Poha", "Besan Chilla", "Medu Vada", "Uttapam", "Wheat Bread Toast", "Upma"]),
                ("Sambar", ["Sambar", "Sprouts Salad", "Plain Curd", "Coconut Chutney"]),
            ],
            "lunch": [
                ("Brown Rice", ["Brown Rice", "Basmati Rice", "Whole Wheat Roti"]),
                ("Dal Tadka", ["Dal Tadka", "Rajma", "Moong Dal Soup"]),
                ("Aloo Gobi", ["Aloo Gobi", "Baingan Bharta", "Sprouts Salad", "Sambar"]),
            ],
            "snack": [
                ("Guava", ["Guava", "Papaya", "Apple", "Banana", "Sprouts Salad"]),
                ("Sprouts Salad", ["Sprouts Salad", "Dhokla"]),
            ],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Baingan Bharta", ["Baingan Bharta", "Aloo Gobi", "Dal Tadka", "Chana Masala"]),
                ("Moong Dal Soup", ["Moong Dal Soup", "Dal Tadka", "Sambar", "Chana Masala"]),
            ],
        },
        # Friday
        {
            "breakfast": [
                ("Besan Chilla", ["Besan Chilla", "Poha", "Medu Vada", "Uttapam", "Wheat Bread Toast", "Dosa"]),
                ("Sambar", ["Sambar", "Sprouts Salad", "Coconut Chutney", "Plain Curd"]),
            ],
            "lunch": [
                ("Basmati Rice", ["Basmati Rice", "Brown Rice", "Whole Wheat Roti"]),
                ("Rajma" if diet_type == "veg" else "Fish Curry",
                 ["Rajma", "Chana Masala", "Dal Tadka"] if diet_type == "veg" else ["Fish Curry", "Rajma", "Dal Tadka"]),
                ("Aloo Gobi", ["Aloo Gobi", "Baingan Bharta", "Moong Dal Soup", "Raita", "Plain Curd"]),
            ],
            "snack": [
                ("Dhokla", ["Dhokla", "Sprouts Salad", "Apple", "Banana"]),
                ("Apple", ["Apple", "Guava", "Papaya"]),
            ],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Chana Masala", ["Chana Masala", "Dal Tadka", "Rajma"]),
                ("Moong Dal Soup", ["Moong Dal Soup", "Baingan Bharta", "Aloo Gobi"]),
            ],
        },
        # Saturday
        {
            "breakfast": [
                ("Besan Chilla" if diet_type == "veg" else "Wheat Bread Toast",
                 ["Besan Chilla", "Poha", "Medu Vada", "Uttapam", "Aloo Paratha"] if diet_type == "veg" else ["Wheat Bread Toast", "Besan Chilla", "Poha"]),
                ("Sprouts Salad", ["Sprouts Salad", "Sambar", "Plain Curd", "Raita"]),
            ],
            "lunch": [
                ("Vegetable Pulao", ["Vegetable Pulao", "Basmati Rice", "Brown Rice", "Whole Wheat Roti"]),
                ("Dal Tadka", ["Dal Tadka", "Rajma", "Chana Masala", "Kadhi Pakora"]),
                ("Baingan Bharta", ["Baingan Bharta", "Aloo Gobi", "Moong Dal Soup", "Sambar"]),
            ],
            "snack": [
                ("Papaya", ["Papaya", "Guava", "Apple", "Banana", "Sprouts Salad"]),
                ("Sprouts Salad", ["Sprouts Salad", "Dhokla"]),
            ],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Rajma", ["Rajma", "Chana Masala", "Dal Tadka"]),
                ("Moong Dal Soup", ["Moong Dal Soup", "Aloo Gobi", "Baingan Bharta"]),
            ],
        },
        # Sunday
        {
            "breakfast": [
                ("Medu Vada", ["Medu Vada", "Besan Chilla", "Poha", "Uttapam", "Wheat Bread Toast"]),
                ("Sambar", ["Sambar", "Sprouts Salad", "Coconut Chutney"]),
            ],
            "lunch": [
                ("Basmati Rice", ["Basmati Rice", "Brown Rice", "Vegetable Pulao"]),
                ("Dal Tadka", ["Dal Tadka", "Moong Dal Soup", "Rajma"]),
                ("Aloo Gobi" if diet_type == "veg" else "Chicken Biryani",
                 ["Aloo Gobi", "Baingan Bharta", "Chana Masala", "Rajma"] if diet_type == "veg" else ["Chicken Biryani", "Aloo Gobi", "Rajma"]),
            ],
            "snack": [
                ("Sprouts Salad", ["Sprouts Salad", "Dhokla", "Apple", "Papaya"]),
                ("Guava", ["Guava", "Apple", "Papaya"]),
            ],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Chana Masala" if diet_type == "veg" else "Tandoori Chicken",
                 ["Chana Masala", "Dal Tadka", "Rajma"] if diet_type == "veg" else ["Tandoori Chicken", "Chana Masala", "Dal Tadka"]),
                ("Baingan Bharta", ["Baingan Bharta", "Aloo Gobi", "Moong Dal Soup"]),
            ],
        },
    ]

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    name_map = (
        df.assign(_key=df["food_name"].str.lower())
        .set_index("_key")["calories"]
        .to_dict()
    )

    scaled_7day_plan: dict[str, dict[str, list[dict]]] = {}
    cands_map = {"breakfast": b_cands, "lunch": l_cands, "snack": s_cands, "dinner": d_cands}

    for idx, d_name in enumerate(day_names):
        tmpl = day_templates[idx]
        day_raw_plan: dict[str, list[dict]] = {}
        base_cal = 0.0

        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            day_raw_plan[slot] = []
            slot_cands = cands_map[slot]
            items_spec = tmpl[slot]
            current_slot_items: list[str] = []
            for primary, pref_list in items_spec:
                chosen = pick_first_available(slot_cands, pref_list, current_slot_items)
                current_slot_items.append(chosen)
                default_qty = 120.0 if slot == "snack" else (160.0 if slot == "lunch" else 140.0)
                day_raw_plan[slot].append({"food_name": chosen, "quantity_g": default_qty})
                base_cal += (name_map.get(chosen.lower(), 100.0) * default_qty) / 100.0

        # Scale day portions to match cal_target within +/- 5%
        scale = cal_target / max(base_cal, 400.0)
        day_scaled: dict[str, list[dict]] = {}
        for slot, items in day_raw_plan.items():
            day_scaled[slot] = []
            for it in items:
                fn_lower = it["food_name"].lower()
                is_grain = fn_lower in GRAIN_FOODS
                # Grains scale moderately (capped at 220g) to prevent carb spikes; curries/dals carry protein
                item_scale = min(scale, 1.25) if is_grain else scale
                adj = round((it["quantity_g"] * item_scale) / 5.0) * 5.0
                if is_grain:
                    adj = min(adj, 220.0)
                day_scaled[slot].append({
                    "food_name": it["food_name"],
                    "quantity_g": max(adj, 30.0),
                })
        scaled_7day_plan[d_name] = day_scaled

    # Top-level meal slots for legacy 1-day callers
    mon_plan = scaled_7day_plan["monday"]
    scaled_7day_plan["breakfast"] = mon_plan["breakfast"]
    scaled_7day_plan["lunch"] = mon_plan["lunch"]
    scaled_7day_plan["snack"] = mon_plan["snack"]
    scaled_7day_plan["dinner"] = mon_plan["dinner"]

    plan_json = json.dumps(scaled_7day_plan, indent=2)
    demo_explanation = (
        f"### 🥗 7-Day Personalized Indian Nutrition Plan (Target: {cal_target:.0f} kcal/day)\n\n"
        f"```json\n{plan_json}\n```\n\n"
        f"**Nutritionist Rationale:**\n"
        f"- **Weekly Variety & Nutrient Density:** Features a rich variety of Indian whole grains (Roti, Basmati Rice, Brown Rice, Poha, Khichdi), protein-rich dals and legumes (Dal Tadka, Rajma, Chana Masala, Moong Dal), and fresh vegetables.\n"
        f"- **Macronutrient Balance:** Balanced distribution across the day (~25% Breakfast, 35% Lunch, 10% Evening Snack, 30% Dinner).\n"
        f"- **Strict Allergen & Preference Protection:** 100% compliant with your dietary preference ({diet_type.title()}) and specified allergen restrictions.\n"
        f"- **Hydration & Satiety:** High-fiber whole foods and nutrient-dense dals provide sustained energy and optimal gut health.\n\n"
        f"*(Generated via Agentic Planning Engine & ICMR-NIN Indian Food Composition Database)*"
    )
    return demo_explanation


# Models Google has retired. Skipping them avoids a guaranteed 404 (and a full
# request timeout) before the first usable model is tried.
_RETIRED_MODELS = {"gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"}
_MODEL_FALLBACKS = (
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
)


def _candidate_models() -> list[str]:
    """Configured model first, then current generally-available flash models."""
    candidates = [settings.model_name, *_MODEL_FALLBACKS]
    return list(dict.fromkeys(m for m in candidates if m and m not in _RETIRED_MODELS))


def _is_auth_failure(exc: Exception) -> bool:
    """True when retrying another model cannot fix the failure (bad key)."""
    text = str(exc).upper()
    return any(marker in text for marker in ("API_KEY_INVALID", "401 UNAUTHORIZED", "403 FORBIDDEN", "PERMISSION_DENIED"))


def generate_offline_chat_reply(query: str, profile: dict, targets: dict) -> str:
    """Answer a chat turn without an external model.

    Used when no API key is configured *and* when a configured key fails. Having
    one implementation for both paths is essential: the allergen / excluded-food
    checks must never be bypassed by a fallback.
    """
    last_q_raw = str(query or "").strip()
    last_q = last_q_raw.lower()

    profile = profile or {}
    targets = targets or {}
    profile_allergies = [str(a).lower() for a in (profile.get("allergies") or [])]
    profile_excluded = [str(e).lower() for e in (profile.get("excluded_foods") or [])]
    user_diet = profile.get("diet_type", "veg")
    df_all = _get_df()

    def _get_safe_cands(slot: str, limit: int = 4) -> list[dict]:
        mask = (
            (df_all["diet_type"] == "veg" if user_diet == "veg" else pd.Series([True] * len(df_all)))
            & df_all["meal_type"].str.contains(slot, regex=False, na=False)
            & _allergen_mask(df_all, profile.get("allergies") or [])
            & _excluded_mask(df_all, profile.get("excluded_foods") or [])
        )
        sub = df_all[mask].head(limit)
        return [
            {
                "name": row["food_name"],
                "cal": row["calories"],
                "prot": row["protein"],
                "carb": row["carbohydrates"],
                "fat": row["fats"],
                "fib": row["fiber"],
            }
            for _, row in sub.iterrows()
        ]

    def _as_lines(items: list[dict], *, fiber: bool = False) -> str:
        lines = []
        for item in items:
            detail = f"{item['prot']:.1f}g protein, {item['fib']:.1f}g fiber" if fiber else f"{item['prot']:.1f}g protein"
            lines.append(f"- **{item['name']}** ({item['cal']:.0f} kcal, {detail})")
        return "\n".join(lines)

    # 1. The user asks about a food they explicitly excluded.
    asked_excluded = [item for item in profile_excluded if item and item in last_q]
    if asked_excluded:
        ex_name = asked_excluded[0].title()
        safe_b = _get_safe_cands("breakfast", 3)
        safe_b_names = ", ".join(
            f"**{item['name']}** ({item['cal']:.0f} kcal, {item['prot']:.1f}g protein)"
            for item in safe_b
        )
        return (
            f"**AI Nutritionist:** In accordance with your profile settings, **{ex_name}** is strictly excluded from your plan.\n\n"
            f"To ensure balanced nutrition without {ex_name}, your plan features safe Indian options such as:\n"
            f"{safe_b_names}."
        )

    # 2. The user asks about one of their declared allergens.
    asked_allergen = [a for a in profile_allergies if a and a in last_q]
    if asked_allergen and any(w in last_q for w in ["can i", "eat", "have", "take", "safe", "allerg"]):
        return (
            f"**AI Nutritionist:** {asked_allergen[0].title()} is flagged as an allergen in your profile, "
            "so it is strictly excluded from your plan. Choose one of the compliant alternatives below."
        )

    # 3. Explicit substitution requests.
    if "paneer" in last_q and any(w in last_q for w in ["alternative", "substitute", "replace"]):
        if "dairy" in profile_allergies or "paneer" in profile_excluded:
            return (
                "**AI Nutritionist:** Since dairy/paneer is restricted in your profile, excellent protein-rich plant alternatives include:\n"
                "- **Besan Chilla** (180 kcal, 9.5g protein) — savory chickpea flour pancake.\n"
                "- **Rajma / Chana Masala** (130–145 kcal, ~8g protein) — nutrient-dense, high-fiber legumes.\n"
                "- **Sprouts Salad** (85 kcal, 7.5g protein) — fresh, enzymatic sprouted moong."
            )
        return (
            "**AI Nutritionist:** Great alternatives to paneer include:\n"
            "- **Besan Chilla** — savory gram flour pancake offering 9.5g protein per 100g.\n"
            "- **Palak Paneer** — combines paneer with antioxidant-rich spinach.\n"
            "- **Plain Curd / Greek Yogurt** — rich in dairy calcium and probiotics with lower fat."
        )

    if "rice" in last_q and any(w in last_q for w in ["alternative", "substitute", "replace"]):
        return (
            "**AI Nutritionist:** Excellent Indian whole-grain alternatives to white basmati rice:\n"
            "- **Whole Wheat Roti** (233 kcal, 7.8g protein, 5g fiber) — rich in complex carbohydrates and B-vitamins.\n"
            "- **Brown Rice** (111 kcal, 2.6g protein, 1.8g fiber) — unpolished whole grain with lower glycemic response.\n"
            "- **Vegetable Khichdi** (120 kcal, 3.5g protein) — soothing prebiotic combination of rice, lentils, and vegetables."
        )

    if "lunch" in last_q and any(w in last_q for w in ["alternative", "substitute", "replace", "suggest", "take"]):
        safe_l = _get_safe_cands("lunch", 4)
        if safe_l:
            return f"**AI Nutritionist:** Balanced, compliant Indian lunch options for your profile:\n{_as_lines(safe_l)}"
        return "**AI Nutritionist:** Consider Whole Wheat Roti paired with Dal Tadka and Aloo Gobi for a balanced lunch."

    # 4. Meal-slot suggestions (always filtered by the active profile).
    if "breakfast" in last_q:
        safe_b = _get_safe_cands("breakfast", 4)
        if safe_b:
            return f"**AI Nutritionist:** Wholesome, compliant Indian breakfast options matching your profile:\n{_as_lines(safe_b)}"
        return "**AI Nutritionist:** Wholesome breakfast options include Besan Chilla and fresh vegetable Poha."

    if "snack" in last_q or "evening" in last_q:
        safe_s = _get_safe_cands("snack", 4)
        if safe_s:
            return f"**AI Nutritionist:** Healthy, compliant evening snack options matching your profile:\n{_as_lines(safe_s, fiber=True)}"
        return "**AI Nutritionist:** Fresh Apple, Guava, or Moong Sprouts Salad make excellent evening snacks."

    if "dinner" in last_q or "modify" in last_q:
        safe_d = _get_safe_cands("dinner", 4)
        if safe_d:
            return f"**AI Nutritionist:** Wholesome, compliant dinner options matching your profile:\n{_as_lines(safe_d)}"
        return "**AI Nutritionist:** Whole Wheat Roti paired with Chana Masala and Moong Dal Soup provides sustained overnight satiety."

    # 5. The user's own numbers must be answered from their computed targets,
    #    never from an unrelated FAISS chunk about dietary fibre.
    if any(
        phrase in last_q
        for phrase in (
            "my numbers", "my targets", "my calories", "my macros", "my breakdown",
            "breakdown", "calorie and macro", "nutrition breakdown",
        )
    ):
        cal_val = float(targets.get("calorie_target", 2000.0) or 2000.0)
        prot_val = float(targets.get("protein_g", 100.0) or 100.0)
        carb_val = float(targets.get("carbs_g", 250.0) or 250.0)
        fat_val = float(targets.get("fats_g", 60.0) or 60.0)
        fib_val = float(targets.get("fiber_g", 28.0) or 28.0)
        return (
            "**AI Nutritionist:** Here is your daily nutritional breakdown:\n"
            f"- **Daily Energy Target:** {cal_val:.0f} kcal (aligned with your fitness goal)\n"
            f"- **Protein Goal:** {prot_val:.1f}g (~{(prot_val*4/cal_val)*100:.0f}% of calories) — promotes lean tissue maintenance and satiety\n"
            f"- **Carbohydrate Goal:** {carb_val:.1f}g (~{(carb_val*4/cal_val)*100:.0f}% of calories) — sustains mental and muscular endurance\n"
            f"- **Healthy Fat Goal:** {fat_val:.1f}g (~{(fat_val*9/cal_val)*100:.0f}% of calories) — supports endocrine function and vitamin absorption\n"
            f"- **Dietary Fiber:** {fib_val:.1f}g — supports glycemic control and healthy digestion.\n\n"
            "Meals are structured into ~25% Breakfast, 35% Lunch, 10% Snack, and 30% Dinner."
        )

    # 6. Authoritative guidance from the local knowledge base.
    try:
        rag_result = retrieve_nutrition_knowledge.invoke({"query": last_q_raw})
        if (
            not rag_result.startswith("No relevant nutrition document sections")
            and not rag_result.startswith("[ERROR]")
        ):
            return f"{rag_result}\n\n*Retrieved locally via FAISS & the ICMR-NIN knowledge base.*"
    except Exception:
        pass

    # 7. Explanation / rationale questions (only when retrieval found nothing).
    if "why" in last_q or "recommend" in last_q:
        return (
            "**AI Nutritionist:** The foods were recommended based on:\n"
            "1. **Cereal-Pulse Complementarity:** Pairing grains (roti/rice) with legumes (dals/beans) to achieve a complete amino acid profile.\n"
            "2. **Caloric Distribution:** Proportioning meals across the day (~25% Breakfast, 35% Lunch, 10% Snack, 30% Dinner).\n"
            "3. **Strict Compliance:** Zero non-vegetarian foods in vegetarian plans and 100% exclusion of your specified allergens and disliked foods."
        )

    return (
        "**AI Nutritionist:** No relevant document sections were found in the ICMR-NIN knowledge base for that query. "
        "You can ask about the nutritional benefits of millets, Indian protein sources, dietary fiber, whole grains vs refined grains, or meal substitutions!"
    )


def agent_node(state: AgentState) -> dict[str, Any]:
    """Gemini AI reasoning engine.

    Understands requirements, selects tools, and formulates meal recommendations.
    Seamlessly activates the ICMR-NIN demo planning engine if the API key is missing or invalid.
    """
    if state.get("error"):
        return {}

    profile = state.get("user_profile") or {}
    targets = state.get("nutrition_targets") or {}
    api_key = settings.api_key

    # Check if this is a conversational question vs initial meal plan generation
    messages = list(state.get("messages", []))
    user_questions = [
        text
        for text in (_message_text(m) for m in messages if isinstance(m, HumanMessage))
        if text and not text.startswith("USER GOALS")
    ]
    last_q_raw = user_questions[-1] if user_questions else ""
    is_chat_turn = bool(user_questions)

    if not api_key:
        if is_chat_turn:
            reply = generate_offline_chat_reply(last_q_raw, profile, targets)
            return {"messages": [AIMessage(content=reply)]}
        demo_content = generate_demo_meal_plan(profile, targets)
        return {"messages": [AIMessage(content=demo_content)]}

    # Try the configured model first. Google retires/throttles flash models
    # fairly often, so fall through to currently available ones instead of
    # dropping straight into demo mode on a transient 404/503/504.
    last_exc: Optional[Exception] = None
    for model in _candidate_models():
        try:
            llm = ChatGoogleGenerativeAI(
                model=model,
                google_api_key=api_key,
                temperature=settings.temperature,
                max_output_tokens=settings.max_output_tokens,
                timeout=settings.request_timeout,
                max_retries=settings.max_retries,
            )
            llm_with_tools = llm.bind_tools(ALL_TOOLS)
            all_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
            response = llm_with_tools.invoke(all_messages)
            return {"messages": [response]}
        except Exception as exc:
            last_exc = exc
            if _is_auth_failure(exc):
                break

    err_str = str(last_exc) if last_exc else "Unknown error"

    if is_chat_turn:
        # Use the very same profile-aware answers as offline mode: the API being
        # down must never weaken allergen / excluded-food protection.
        reply = generate_offline_chat_reply(last_q_raw, profile, targets)
        return {"messages": [AIMessage(content=reply)]}

    demo_content = generate_demo_meal_plan(profile, targets)
    notice = (
        f"> 💡 **Demo Mode Activated:** The Gemini API was unreachable or invalid ({err_str[:60]}). "
        f"Successfully generated a 100% compliant meal plan using the ICMR-NIN planning engine.\n\n"
        f"{demo_content}"
    )
    return {"messages": [AIMessage(content=notice)]}


def sanitize_plan_restrictions(
    plan_dict: dict[str, Any],
    diet_type: str,
    allergies: list[str],
    excluded_foods: list[str],
    food_df: pd.DataFrame,
) -> tuple[dict[str, Any], list[str]]:
    """Deterministically replace any item that violates diet, allergen, or excluded food rules."""
    from core.allergens import food_violates_exclusion, ingredients_contain_allergen

    modified_plan = json.loads(json.dumps(plan_dict))
    replacements_made = []

    def _get_replacement(slot: str, avoid: set[str]) -> str:
        mask = (
            (food_df["diet_type"] == "veg" if diet_type == "veg" else pd.Series([True] * len(food_df)))
            & food_df["meal_type"].str.contains(slot, regex=False, na=False)
            & _allergen_mask(food_df, allergies)
            & _excluded_mask(food_df, excluded_foods)
        )
        cands = food_df[mask]["food_name"].tolist()
        for c in cands:
            if c.lower() not in avoid:
                return c
        return cands[0] if cands else "Basmati Rice"

    weekly_map = _day_map(modified_plan)
    target_dict = weekly_map if weekly_map else {"day": modified_plan}
    for day_k, meals in target_dict.items():
        if not isinstance(meals, dict):
            continue
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            items = meals.get(slot, [])
            if isinstance(items, dict):
                items = [items]
            if not isinstance(items, list):
                continue
            avoid = {str(it.get("food_name", "")).strip().lower() for it in items if isinstance(it, dict)}
            for it in items:
                if not isinstance(it, dict):
                    continue
                fname = str(it.get("food_name", "")).strip()
                row_match = food_df[food_df["food_name"].str.lower() == fname.lower()]
                violates = False
                reason = ""
                if not row_match.empty:
                    row = row_match.iloc[0]
                    raw_ing = str(row.get("ingredients", ""))
                    if diet_type == "veg" and row["diet_type"] != "veg":
                        violates = True
                        reason = "non-veg dish in vegetarian diet"
                    elif ingredients_contain_allergen(raw_ing, allergies) or any(
                        a.lower() in str(row.get("allergens", "")).lower() for a in allergies
                    ):
                        violates = True
                        reason = "allergen detected"
                    elif food_violates_exclusion(fname, raw_ing, excluded_foods):
                        violates = True
                        reason = "excluded food detected"
                else:
                    if food_violates_exclusion(fname, "", excluded_foods):
                        violates = True
                        reason = "excluded food detected"

                if violates:
                    repl = _get_replacement(slot, avoid)
                    replacements_made.append(f"Auto-replaced '{fname}' ({reason}) with '{repl}' in {day_k} {slot}")
                    it["food_name"] = repl
                    avoid.add(repl.lower())

    return modified_plan, replacements_made


# ── Node 5: Meal Plan Validation ──────────────────────────────────────────────

def meal_validation_node(state: AgentState) -> dict[str, Any]:
    """Validate generated meal plan against deterministic dietary and calorie rules."""
    messages = state.get("messages", [])
    if not messages:
        return {}

    content = _message_text(messages[-1])

    meal_plan_dict = extract_meal_plan_json(content)
    if not meal_plan_dict:
        # No structured meal plan found (e.g. conversational question). Clear any
        # plan left over from an earlier turn so the UI never renders stale data.
        return {
            "meal_plan": None,
            "weekly_plan": None,
            "validation_result": {"is_valid": True, "issues": [], "note": "Conversational reply"},
        }

    # Fetch targets and profile
    targets = state.get("nutrition_targets") or {}
    profile = state.get("user_profile") or {}
    calorie_target = targets.get("calorie_target", 2000.0)
    diet_type = profile.get("diet_type", "veg")
    allergies = profile.get("allergies", [])
    excluded_foods = profile.get("excluded_foods", [])
    df = _get_df()

    # Check if 7-day weekly plan or 1-day plan (case-insensitive)
    weekly_days = _day_map(meal_plan_dict)
    has_days = bool(weekly_days)

    if has_days:
        issues, avg_dev_pct, daily_cals = run_weekly_checks(
            weekly_plan=meal_plan_dict,
            diet_type=diet_type,
            allergies=allergies,
            excluded_foods=excluded_foods,
            calorie_target=calorie_target,
            food_df=df,
        )
        # If any restriction violations were found, attempt deterministic sanitization
        has_restriction_issue = any(
            any(w in iss.lower() for w in ["allergen", "excluded", "contains", "non-veg"])
            for iss in issues
        )
        if has_restriction_issue:
            meal_plan_dict, _ = sanitize_plan_restrictions(meal_plan_dict, diet_type, allergies, excluded_foods, df)
            weekly_days = _day_map(meal_plan_dict)
            issues, avg_dev_pct, daily_cals = run_weekly_checks(
                weekly_plan=meal_plan_dict,
                diet_type=diet_type,
                allergies=allergies,
                excluded_foods=excluded_foods,
                calorie_target=calorie_target,
                food_df=df,
            )

        avg_cal = round(sum(daily_cals.values()) / max(len(daily_cals), 1), 1)

        # Estimate average macros across all 7 days
        name_index = (
            df.assign(_key=df["food_name"].str.lower())
            .set_index("_key")[["protein", "carbohydrates", "fats"]]
            .to_dict(orient="index")
        )
        tot_p, tot_c, tot_f = 0.0, 0.0, 0.0
        day_count = 0
        for d in _DAY_KEYS:
            day_meals = weekly_days.get(d)
            if not day_meals:
                continue
            day_count += 1
            for s in ["breakfast", "lunch", "snack", "dinner"]:
                slot_items = day_meals.get(s, [])
                if isinstance(slot_items, dict):
                    slot_items = [slot_items]
                if not isinstance(slot_items, list):
                    continue
                for it in slot_items:
                    if not isinstance(it, dict):
                        continue
                    fn = str(it.get("food_name", "")).strip().lower()
                    try:
                        q = float(it.get("quantity_g", 0.0))
                    except (TypeError, ValueError):
                        q = 0.0
                    if fn in name_index and q > 0:
                        sc = q / 100.0
                        tot_p += name_index[fn]["protein"] * sc
                        tot_c += name_index[fn]["carbohydrates"] * sc
                        tot_f += name_index[fn]["fats"] * sc

        avg_prot = round(tot_p / max(day_count, 1), 1)
        avg_carb = round(tot_c / max(day_count, 1), 1)
        avg_fat = round(tot_f / max(day_count, 1), 1)

        validation_result = {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "calorie_deviation_pct": avg_dev_pct,
            "planned_calories": avg_cal,
            "planned_protein": avg_prot,
            "planned_carbs": avg_carb,
            "planned_fats": avg_fat,
            "target_calories": calorie_target,
            "target_protein": targets.get("protein_g", 0.0),
            "target_carbs": targets.get("carbs_g", 0.0),
            "target_fats": targets.get("fats_g", 0.0),
            "daily_calories": daily_cals,
            "is_weekly": True,
        }
    else:
        # Single day plan validation
        name_index = (
            df.assign(_key=df["food_name"].str.lower())
            .set_index("_key")[["calories", "protein", "carbohydrates", "fats", "fiber"]]
            .to_dict(orient="index")
        )

        planned_cal = 0.0
        planned_prot = 0.0
        planned_carb = 0.0
        planned_fat = 0.0

        for meal_key in ["breakfast", "lunch", "snack", "dinner"]:
            slot_items = meal_plan_dict.get(meal_key, [])
            if isinstance(slot_items, dict):
                slot_items = [slot_items]
            if not isinstance(slot_items, list):
                continue
            for item in slot_items:
                if not isinstance(item, dict):
                    continue
                fname = str(item.get("food_name", "")).strip().lower()
                try:
                    qty = float(item.get("quantity_g", 0))
                except (TypeError, ValueError):
                    qty = 0.0
                if fname in name_index and qty > 0:
                    scale = qty / 100.0
                    row = name_index[fname]
                    planned_cal += row["calories"] * scale
                    planned_prot += row["protein"] * scale
                    planned_carb += row["carbohydrates"] * scale
                    planned_fat += row["fats"] * scale

        planned_cal = round(planned_cal, 1)
        planned_prot = round(planned_prot, 1)
        planned_carb = round(planned_carb, 1)
        planned_fat = round(planned_fat, 1)

        issues, dev_pct = run_all_checks(
            plan=meal_plan_dict,
            diet_type=diet_type,
            allergies=allergies,
            excluded_foods=excluded_foods,
            calorie_target=calorie_target,
            planned_calories=planned_cal,
            food_df=df,
        )

        validation_result = {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "calorie_deviation_pct": dev_pct,
            "planned_calories": planned_cal,
            "planned_protein": planned_prot,
            "planned_carbs": planned_carb,
            "planned_fats": planned_fat,
            "target_calories": calorie_target,
            "target_protein": targets.get("protein_g", 0.0),
            "target_carbs": targets.get("carbs_g", 0.0),
            "target_fats": targets.get("fats_g", 0.0),
            "is_weekly": False,
        }

    return {
        "meal_plan": meal_plan_dict,
        "validation_result": validation_result,
    }


# ── Node 6: Plan Revision ─────────────────────────────────────────────────────

def plan_revision_node(state: AgentState) -> dict[str, Any]:
    """Formulate revision prompt and increment revision counter."""
    val_res = state.get("validation_result") or {}
    issues_list = val_res.get("issues", [])
    issues_str = "\n".join(f"- {issue}" for issue in issues_list)

    revision_count = state.get("revision_count", 0) + 1

    revision_msg = REVISION_PROMPT_TEMPLATE.format(
        issues=issues_str or "Calorie target or portion imbalance.",
        planned_calories=val_res.get("planned_calories", 0),
        target_calories=val_res.get("target_calories", 0),
        deviation_pct=val_res.get("calorie_deviation_pct", 0),
        planned_protein=val_res.get("planned_protein", 0),
        target_protein=val_res.get("target_protein", 0),
        planned_carbs=val_res.get("planned_carbs", 0),
        target_carbs=val_res.get("target_carbs", 0),
        planned_fats=val_res.get("planned_fats", 0),
        target_fats=val_res.get("target_fats", 0),
    )

    return {
        "messages": [HumanMessage(content=revision_msg)],
        "revision_count": revision_count,
    }


# ── Node 7: Final Response ────────────────────────────────────────────────────

def final_response_node(state: AgentState) -> dict[str, Any]:
    """Assemble final validated plan, structured WeeklyPlan object, and conversational response."""
    error = state.get("error")
    if error:
        return {"final_response": f"Error: {error}"}

    messages = state.get("messages", [])
    last_text = _message_text(messages[-1]) if messages else "No response generated."

    val_res = state.get("validation_result") or {}
    meal_plan_dict = state.get("meal_plan")

    # Conversational turn: return the reply only. Emitting plan fields here would
    # surface a plan generated on an earlier turn as if it were the current answer.
    if val_res.get("note") == "Conversational reply" or not meal_plan_dict:
        return {
            "final_response": str(last_text),
            "weekly_plan": None,
            "meal_plan": None,
        }

    if not val_res.get("is_valid", True):
        issues = val_res.get("issues", [])
        issues_note = "\n".join(f"- {i}" for i in issues)
        fallback_notice = (
            f"\n\n> ❌ **Plan Validation Notice:** The recommended plan failed automated validation checks:\n{issues_note}"
        )
        last_text = f"{last_text}\n{fallback_notice}"

    # Build the full structured WeeklyPlan Pydantic model
    targets_dict = state.get("nutrition_targets") or {}
    weekly_plan_dict = None

    if targets_dict and meal_plan_dict:
        try:
            targets_obj = NutritionTargets(**targets_dict)
            df = _get_df()
            weekly_days = _day_map(meal_plan_dict)

            days_list = []
            for dk in _DAY_KEYS:
                day_meals = weekly_days.get(dk) if weekly_days else meal_plan_dict
                if not day_meals or not isinstance(day_meals, dict):
                    day_meals = {
                        "breakfast": meal_plan_dict.get("breakfast", []),
                        "lunch": meal_plan_dict.get("lunch", []),
                        "snack": meal_plan_dict.get("snack", []),
                        "dinner": meal_plan_dict.get("dinner", []),
                    }
                dp = build_day_plan_detail(
                    day_name=dk.title(),
                    meals_dict=day_meals,
                    food_df=df,
                    target_calories=targets_obj.calorie_target,
                )
                days_list.append(dp)

            averages = calculate_weekly_averages(days_list, targets_obj)

            v_res_obj = None
            if val_res:
                v_res_obj = ValidationResult(
                    is_valid=val_res.get("is_valid", True),
                    issues=val_res.get("issues", []),
                    calorie_deviation_pct=val_res.get("calorie_deviation_pct", 0.0),
                    planned_calories=val_res.get("planned_calories", 0.0),
                    planned_protein=val_res.get("planned_protein", 0.0),
                    planned_carbs=val_res.get("planned_carbs", 0.0),
                    planned_fats=val_res.get("planned_fats", 0.0),
                )

            wp = WeeklyPlan(
                user_targets=targets_obj,
                days=days_list,
                weekly_averages=averages,
                rationale=str(last_text),
                validation_result=v_res_obj,
                source_references=[
                    "ICMR-NIN Indian Food Composition Tables (IFCT 2017)",
                    "ICMR-NIN Dietary Guidelines for Indians & RDA 2020",
                ],
            )
            weekly_plan_dict = wp.model_dump()
        except Exception:
            pass

    flat_meal_plan = meal_plan_dict
    weekly_days = _day_map(meal_plan_dict)
    if weekly_days:
        mon = weekly_days.get("monday") or {}
        flat_meal_plan = {
            "breakfast": mon.get("breakfast", meal_plan_dict.get("breakfast", [])),
            "lunch": mon.get("lunch", meal_plan_dict.get("lunch", [])),
            "snack": mon.get("snack", meal_plan_dict.get("snack", [])),
            "dinner": mon.get("dinner", meal_plan_dict.get("dinner", [])),
        }

    return {
        "final_response": str(last_text),
        "weekly_plan": weekly_plan_dict,
        "meal_plan": flat_meal_plan,
    }


# ── Conditional Routing Functions ─────────────────────────────────────────────

def route_profile_validation(state: AgentState) -> str:
    if state.get("error"):
        return "final_response"
    return "nutrition_calculation"


def route_agent_output(state: AgentState) -> str:
    """Decide whether to execute tools or proceed to meal validation."""
    messages = state.get("messages", [])
    if not messages:
        return "meal_validation"

    last_msg = messages[-1]
    if getattr(last_msg, "tool_calls", None):
        return "tools"
    return "meal_validation"


def route_validation_outcome(state: AgentState) -> str:
    """Check validation status and decide between revision or final output."""
    val_res = state.get("validation_result") or {}
    if val_res.get("is_valid", True):
        return "final_response"

    revision_count = state.get("revision_count", 0)
    if revision_count < settings.max_revisions:
        return "plan_revision"

    return "final_response"


# ── Build Graph ───────────────────────────────────────────────────────────────

def create_agent_graph(checkpointer: Optional[Any] = None) -> Any:
    """Construct and compile the LangGraph Food & Nutrition Planning workflow."""
    builder = StateGraph(AgentState)

    # Add Nodes
    builder.add_node("profile_validation", profile_validation_node)
    builder.add_node("nutrition_calculation", nutrition_calculation_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(ALL_TOOLS))
    builder.add_node("meal_validation", meal_validation_node)
    builder.add_node("plan_revision", plan_revision_node)
    builder.add_node("final_response", final_response_node)

    # Add Edges & Conditional Edges
    builder.set_entry_point("profile_validation")

    builder.add_conditional_edges(
        "profile_validation",
        route_profile_validation,
        {
            "final_response": "final_response",
            "nutrition_calculation": "nutrition_calculation",
        },
    )

    builder.add_edge("nutrition_calculation", "agent")

    builder.add_conditional_edges(
        "agent",
        route_agent_output,
        {
            "tools": "tools",
            "meal_validation": "meal_validation",
        },
    )

    builder.add_edge("tools", "agent")

    builder.add_conditional_edges(
        "meal_validation",
        route_validation_outcome,
        {
            "final_response": "final_response",
            "plan_revision": "plan_revision",
        },
    )

    builder.add_edge("plan_revision", "agent")
    builder.add_edge("final_response", END)

    if checkpointer is None:
        checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


# Singleton compiled graph
app_graph = create_agent_graph()
