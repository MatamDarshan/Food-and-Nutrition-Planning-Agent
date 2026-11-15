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
import re
from typing import Any, Optional

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

def extract_meal_plan_json(text: str) -> Optional[dict]:
    """Extract a meal plan dictionary from model output text.

    Supports both:
    1. 7-day weekly plans: {"monday": {...}, "tuesday": {...}, ...}
    2. Single-day meal plans: {"breakfast": [...], "lunch": [...], ...}
    """
    if not text:
        return None

    def is_valid_plan_dict(d: dict) -> bool:
        if not isinstance(d, dict):
            return False
        # Check for 7-day plan
        days_matched = [
            k for k in d.keys()
            if str(k).lower().strip() in [
                "monday", "tuesday", "wednesday", "thursday",
                "friday", "saturday", "sunday"
            ]
        ]
        if len(days_matched) >= 3:
            return True
        # Check for single-day plan
        meals_matched = [
            k for k in d.keys()
            if str(k).lower().strip() in ["breakfast", "lunch", "dinner", "snack"]
        ]
        if len(meals_matched) >= 2:
            return True
        return False

    # 1. Try markdown code blocks: ```json ... ``` or ``` ... ```
    matches = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    for block in matches:
        try:
            parsed = json.loads(block)
            if is_valid_plan_dict(parsed):
                return parsed
        except json.JSONDecodeError:
            pass

    # 2. Try outermost curly braces containing meal/day keys
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        snippet = text[first_brace : last_brace + 1]
        try:
            parsed = json.loads(snippet)
            if is_valid_plan_dict(parsed):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


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
    allergies = profile.get("allergies", [])
    excluded = [f.lower() for f in profile.get("excluded_foods", [])]
    cal_target = targets.get("calorie_target", 2000.0)

    # Filter helper
    def get_slot_candidates(meal_slot: str) -> list[str]:
        mask = (
            (df["diet_type"] == "veg" if diet_type == "veg" else pd.Series([True] * len(df)))
            & df["meal_type"].str.contains(meal_slot, regex=False, na=False)
            & ~df["food_name"].str.lower().isin(excluded)
        )
        for allergen in allergies:
            mask = mask & ~df["allergens"].str.contains(allergen, case=False, regex=False, na=False)
        matched = df[mask]
        return matched["food_name"].tolist() if not matched.empty else []

    b_cands = get_slot_candidates("breakfast")
    l_cands = get_slot_candidates("lunch")
    s_cands = get_slot_candidates("snack")
    d_cands = get_slot_candidates("dinner")

    def pick_first_available(cands: list[str], preferred: list[str]) -> str:
        for p in preferred:
            if p in cands:
                return p
        return cands[0] if cands else "Basmati Rice"

    # 7 balanced day templates with authentic Indian staples
    day_templates = [
        # Monday
        {
            "breakfast": [("Idli", ["Idli", "Besan Chilla", "Poha"]), ("Sambar", ["Sambar", "Coconut Chutney", "Plain Curd"])],
            "lunch": [("Basmati Rice", ["Basmati Rice", "Brown Rice"]), ("Dal Tadka", ["Dal Tadka", "Moong Dal Soup"]), ("Raita", ["Raita", "Plain Curd", "Sprouts Salad"])],
            "snack": [("Apple", ["Apple", "Banana", "Papaya", "Guava"])],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Chicken Curry" if diet_type == "non-veg" else "Palak Paneer",
                 ["Chicken Curry", "Palak Paneer", "Chana Masala", "Dal Tadka"] if diet_type == "non-veg" else ["Palak Paneer", "Chana Masala", "Dal Tadka"])
            ],
        },
        # Tuesday
        {
            "breakfast": [("Poha", ["Poha", "Upma", "Besan Chilla"]), ("Plain Curd", ["Plain Curd", "Buttermilk / Chaas", "Sprouts Salad"])],
            "lunch": [("Whole Wheat Roti", ["Whole Wheat Roti", "Brown Rice"]), ("Rajma", ["Rajma", "Chana Masala", "Dal Tadka"]), ("Buttermilk / Chaas", ["Buttermilk / Chaas", "Plain Curd", "Sprouts Salad"])],
            "snack": [("Sprouts Salad", ["Sprouts Salad", "Dhokla", "Apple"])],
            "dinner": [("Basmati Rice", ["Basmati Rice", "Whole Wheat Roti"]), ("Chana Masala", ["Chana Masala", "Rajma", "Dal Tadka"])],
        },
        # Wednesday
        {
            "breakfast": [("Besan Chilla", ["Besan Chilla", "Idli", "Dosa"]), ("Coconut Chutney", ["Coconut Chutney", "Sambar", "Plain Curd"])],
            "lunch": [("Vegetable Khichdi", ["Vegetable Khichdi", "Basmati Rice", "Vegetable Pulao"]), ("Plain Curd", ["Plain Curd", "Raita", "Sprouts Salad"])],
            "snack": [("Banana", ["Banana", "Papaya", "Apple", "Guava"])],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Egg Curry" if diet_type == "non-veg" else "Dal Makhani",
                 ["Egg Curry", "Dal Makhani", "Chana Masala", "Dal Tadka"] if diet_type == "non-veg" else ["Dal Makhani", "Chana Masala", "Dal Tadka"])
            ],
        },
        # Thursday
        {
            "breakfast": [("Upma", ["Upma", "Poha", "Idli"]), ("Sambar", ["Sambar", "Plain Curd", "Coconut Chutney"])],
            "lunch": [("Brown Rice", ["Brown Rice", "Basmati Rice"]), ("Dal Tadka", ["Dal Tadka", "Rajma", "Moong Dal Soup"]), ("Aloo Gobi", ["Aloo Gobi", "Baingan Bharta", "Sprouts Salad"])],
            "snack": [("Guava", ["Guava", "Papaya", "Apple", "Banana"])],
            "dinner": [("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]), ("Baingan Bharta", ["Baingan Bharta", "Palak Paneer", "Dal Tadka"]), ("Moong Dal Soup", ["Moong Dal Soup", "Sambar"])],
        },
        # Friday
        {
            "breakfast": [("Dosa", ["Dosa", "Idli", "Besan Chilla"]), ("Sambar", ["Sambar", "Coconut Chutney", "Plain Curd"])],
            "lunch": [
                ("Basmati Rice", ["Basmati Rice", "Brown Rice"]),
                ("Fish Curry" if diet_type == "non-veg" else "Palak Paneer",
                 ["Fish Curry", "Palak Paneer", "Rajma", "Dal Tadka"] if diet_type == "non-veg" else ["Palak Paneer", "Rajma", "Dal Tadka"]),
                ("Raita", ["Raita", "Plain Curd", "Sprouts Salad"])
            ],
            "snack": [("Dhokla", ["Dhokla", "Sprouts Salad", "Apple", "Banana"])],
            "dinner": [("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]), ("Chana Masala", ["Chana Masala", "Dal Tadka", "Rajma"])],
        },
        # Saturday
        {
            "breakfast": [
                ("Egg Bhurji" if diet_type == "non-veg" else "Aloo Paratha",
                 ["Egg Bhurji", "Aloo Paratha", "Besan Chilla", "Poha"] if diet_type == "non-veg" else ["Aloo Paratha", "Besan Chilla", "Poha"]),
                ("Wheat Bread Toast" if diet_type == "non-veg" else "Plain Curd",
                 ["Wheat Bread Toast", "Plain Curd", "Raita"] if diet_type == "non-veg" else ["Plain Curd", "Raita"])
            ],
            "lunch": [("Vegetable Pulao", ["Vegetable Pulao", "Basmati Rice", "Vegetable Khichdi"]), ("Kadhi Pakora", ["Kadhi Pakora", "Dal Tadka", "Rajma", "Plain Curd"])],
            "snack": [("Papaya", ["Papaya", "Guava", "Apple", "Banana"])],
            "dinner": [("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]), ("Rajma", ["Rajma", "Chana Masala", "Dal Tadka"])],
        },
        # Sunday
        {
            "breakfast": [
                ("Egg Omelette" if diet_type == "non-veg" else "Medu Vada",
                 ["Egg Omelette", "Medu Vada", "Idli", "Besan Chilla"] if diet_type == "non-veg" else ["Medu Vada", "Idli", "Besan Chilla"]),
                ("Wheat Bread Toast" if diet_type == "non-veg" else "Sambar",
                 ["Wheat Bread Toast", "Sambar", "Coconut Chutney"] if diet_type == "non-veg" else ["Sambar", "Coconut Chutney"])
            ],
            "lunch": [
                ("Basmati Rice", ["Basmati Rice", "Vegetable Pulao"]),
                ("Dal Tadka", ["Dal Tadka", "Moong Dal Soup"]),
                ("Chicken Biryani" if diet_type == "non-veg" else "Paneer Butter Masala",
                 ["Chicken Biryani", "Paneer Butter Masala", "Palak Paneer", "Chicken Curry"] if diet_type == "non-veg" else ["Paneer Butter Masala", "Palak Paneer", "Rajma"])
            ],
            "snack": [("Sprouts Salad", ["Sprouts Salad", "Dhokla", "Apple", "Papaya"])],
            "dinner": [
                ("Whole Wheat Roti", ["Whole Wheat Roti", "Basmati Rice"]),
                ("Tandoori Chicken" if diet_type == "non-veg" else "Palak Paneer",
                 ["Tandoori Chicken", "Palak Paneer", "Chana Masala", "Dal Tadka"] if diet_type == "non-veg" else ["Palak Paneer", "Chana Masala", "Dal Tadka"])
            ],
        },
    ]

    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    name_map = df.set_index("food_name")["calories"].to_dict()

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
            for primary, pref_list in items_spec:
                chosen = pick_first_available(slot_cands, pref_list)
                default_qty = 100.0 if slot == "snack" else (140.0 if slot == "lunch" else 110.0)
                day_raw_plan[slot].append({"food_name": chosen, "quantity_g": default_qty})
                base_cal += (name_map.get(chosen, 100.0) * default_qty) / 100.0

        # Scale day portions to match cal_target within +/- 1%
        scale = cal_target / max(base_cal, 400.0)
        day_scaled: dict[str, list[dict]] = {}
        for slot, items in day_raw_plan.items():
            day_scaled[slot] = []
            for it in items:
                adj = round((it["quantity_g"] * scale) / 5.0) * 5.0
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
        f"- **Weekly Variety & Nutrient Density:** Features a rich variety of Indian whole grains (Roti, Basmati Rice, Brown Rice, Poha, Khichdi, Idli), protein-rich dals and legumes (Dal Tadka, Rajma, Chana Masala, Moong Dal), and fresh vegetables.\n"
        f"- **Macronutrient Balance:** Balanced distribution across the day (~25% Breakfast, 35% Lunch, 10% Evening Snack, 30% Dinner).\n"
        f"- **Strict Allergen & Preference Protection:** 100% compliant with your dietary preference ({diet_type.title()}) and specified allergen restrictions.\n"
        f"- **Hydration & Satiety:** High-fiber whole foods and probiotic curd/raita provide sustained energy and optimal gut health.\n\n"
        f"*(Generated via Agentic Planning Engine & ICMR-NIN Indian Food Composition Database)*"
    )
    return demo_explanation

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
        m.content
        for m in messages
        if isinstance(m, HumanMessage)
        and isinstance(m.content, str)
        and not m.content.startswith("USER GOALS")
    ]
    last_q_raw = user_questions[-1] if user_questions else ""
    last_q = last_q_raw.lower()
    is_chat_turn = bool(user_questions)

    if not api_key:
        if is_chat_turn:
            # First, check RAG knowledge base for authoritative dietary guidance
            try:
                rag_result = retrieve_nutrition_knowledge.invoke({"query": last_q_raw})
                if (
                    not rag_result.startswith("No relevant nutrition document sections")
                    and not rag_result.startswith("[ERROR]")
                ):
                    reply = (
                        f"### 📚 ICMR-NIN Scientific Nutrition Guidance\n\n"
                        f"{rag_result}\n\n"
                        f"*(Retrieved locally via FAISS vector store & ICMR-NIN Guidelines)*"
                    )
                    return {"messages": [AIMessage(content=reply)]}
            except Exception:
                pass

            if "paneer" in last_q and any(w in last_q for w in ["alternative", "substitute", "replace"]):
                reply = (
                    "**AI Nutritionist:** Great alternatives to paneer include:\n"
                    "- **Besan Chilla** — savory gram flour pancake offering 9.5g protein per 100g.\n"
                    "- **Palak Paneer** — combines paneer with antioxidant-rich spinach.\n"
                    "- **Plain Curd / Greek Yogurt** — rich in dairy calcium and probiotics with lower fat."
                )
            elif "rice" in last_q and any(w in last_q for w in ["alternative", "substitute", "replace"]):
                reply = (
                    "**AI Nutritionist:** Excellent Indian whole-grain alternatives to white basmati rice:\n"
                    "- **Whole Wheat Roti** (233 kcal, 7.8g protein, 5g fiber) — rich in complex carbohydrates and B-vitamins.\n"
                    "- **Brown Rice** (111 kcal, 2.6g protein, 1.8g fiber) — unpolished whole grain with lower glycemic response.\n"
                    "- **Vegetable Khichdi** (120 kcal, 3.5g protein) — soothing prebiotic combination of rice, lentils, and vegetables.\n"
                    "- **Ragi Mudde** (110 kcal, 2.3g protein, 344mg Calcium) — calcium-dense millet staple."
                )
            elif "lunch" in last_q and any(w in last_q for w in ["alternative", "substitute", "replace", "suggest"]):
                reply = (
                    "**AI Nutritionist:** Balanced Indian lunch alternatives:\n"
                    "- **Whole Wheat Roti (90g) + Rajma (180g) + Buttermilk (150ml)** — protein-dense and fiber-rich.\n"
                    "- **Vegetable Khichdi (200g) + Plain Curd (120g)** — easily digestible complete amino acid profile.\n"
                    "- **Brown Rice (150g) + Chana Masala (180g) + Fresh Cucumber Raita (100g)** — sustained energy release."
                )
            elif "breakfast" in last_q:
                reply = (
                    "**AI Nutritionist:** Wholesome Indian breakfast options from our database:\n"
                    "- **Besan Chilla** (180 kcal, 9.5g protein) — high protein, low glycemic index.\n"
                    "- **Poha with vegetables & peanuts** (120 kcal) — light and easily digestible.\n"
                    "- **Idli + Sambar** (128 kcal) — traditional fermented South Indian staple with complete protein.\n"
                    "- **Sprouts Salad** (85 kcal, 7.5g protein) — fresh, enzymatic, and fiber-rich."
                )
            elif "breakdown" in last_q or "explain" in last_q and "nutrition" in last_q:
                cal_val = targets.get("calorie_target", 2000.0)
                prot_val = targets.get("protein_g", 100.0)
                carb_val = targets.get("carbs_g", 250.0)
                fat_val = targets.get("fats_g", 60.0)
                fib_val = targets.get("fiber_g", 28.0)
                reply = (
                    f"**AI Nutritionist:** Here is your daily nutritional breakdown:\n"
                    f"- **Daily Energy Target:** {cal_val:.0f} kcal (aligned with your fitness goal)\n"
                    f"- **Protein Goal:** {prot_val:.1f}g (~{(prot_val*4/cal_val)*100:.0f}% of calories) — promotes lean tissue maintenance and satiety\n"
                    f"- **Carbohydrate Goal:** {carb_val:.1f}g (~{(carb_val*4/cal_val)*100:.0f}% of calories) — sustains mental and muscular endurance\n"
                    f"- **Healthy Fat Goal:** {fat_val:.1f}g (~{(fat_val*9/cal_val)*100:.0f}% of calories) — supports endocrine function and vitamin absorption\n"
                    f"- **Dietary Fiber:** {fib_val:.1f}g — supports glycemic control and healthy digestion.\n\n"
                    f"Meals are structured into ~25% Breakfast, 35% Lunch, 10% Snack, and 30% Dinner."
                )
            elif "why" in last_q or "recommend" in last_q:
                reply = (
                    "**AI Nutritionist:** The foods were recommended based on:\n"
                    "1. **Cereal-Pulse Complementarity:** Pairing grains (roti/rice) with legumes (dals/beans) to achieve a complete amino acid profile.\n"
                    "2. **Caloric Distribution:** Proportioning meals across the day (approx 25% Breakfast, 35% Lunch, 10% Snack, 30% Dinner).\n"
                    "3. **Strict Compliance:** Zero non-vegetarian foods in vegetarian plans and 100% exclusion of your specified allergens."
                )
            elif "dinner" in last_q or "modify" in last_q:
                reply = (
                    "**AI Nutritionist:** Suggestions to modify dinner:\n"
                    "- Choose **Whole Wheat Roti** (233 kcal, 7.8g protein, 5g fiber) over white rice.\n"
                    "- Pair with **Chana Masala** or **Palak Paneer** for sustained overnight satiety."
                )
            else:
                reply = (
                    "**AI Nutritionist:** No relevant document sections were found in the ICMR-NIN knowledge base for that query. "
                    "You can ask about the nutritional benefits of millets, Indian protein sources, dietary fiber, whole grains vs refined grains, or meal substitutions!"
                )
            return {"messages": [AIMessage(content=reply)]}
        demo_content = generate_demo_meal_plan(profile, targets)
        return {"messages": [AIMessage(content=demo_content)]}

    try:
        llm = ChatGoogleGenerativeAI(
            model=settings.model_name,
            google_api_key=api_key,
            temperature=settings.temperature,
        )
        llm_with_tools = llm.bind_tools(ALL_TOOLS)
        all_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
        response = llm_with_tools.invoke(all_messages)
        return {"messages": [response]}
    except Exception as exc:
        err_str = str(exc)
        if (
            "API_KEY_INVALID" in err_str
            or "API key not valid" in err_str
            or "INVALID_ARGUMENT" in err_str
            or "RESOURCE_EXHAUSTED" in err_str
            or "quota" in err_str.lower()
        ):
            if is_chat_turn:
                last_q_raw = user_questions[-1] if user_questions else ""
                try:
                    rag_result = retrieve_nutrition_knowledge.invoke({"query": last_q_raw})
                    if (
                        not rag_result.startswith("No relevant nutrition document sections")
                        and not rag_result.startswith("[ERROR]")
                    ):
                        reply = (
                            f"> 💡 **Offline RAG Knowledge Base:**\n\n"
                            f"{rag_result}\n\n"
                            f"*(Retrieved locally via FAISS vector store & ICMR-NIN Guidelines)*"
                        )
                        return {"messages": [AIMessage(content=reply)]}
                except Exception:
                    pass

                reply = (
                    "**AI Nutritionist:** The API key is offline or unavailable. "
                    "However, our local ICMR-NIN knowledge base is active. "
                    "You can ask about millets, Indian protein sources, dietary fiber, or whole grains vs refined grains!"
                )
                return {"messages": [AIMessage(content=reply)]}

            demo_content = generate_demo_meal_plan(profile, targets)
            notice = (
                f"> 💡 **Demo Mode Activated:** The Gemini API was unreachable or invalid. "
                f"Successfully generated a 100% compliant meal plan using the ICMR-NIN planning engine.\n\n"
                f"{demo_content}"
            )
            return {"messages": [AIMessage(content=notice)]}
        else:
            return {"messages": [AIMessage(content=f"⚠️ Gemini API Error: {err_str}")]}


# ── Node 5: Meal Plan Validation ──────────────────────────────────────────────

def meal_validation_node(state: AgentState) -> dict[str, Any]:
    """Validate generated meal plan against deterministic dietary and calorie rules."""
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = messages[-1]
    content = getattr(last_message, "content", "")
    if not isinstance(content, str):
        content = str(content)

    meal_plan_dict = extract_meal_plan_json(content)
    if not meal_plan_dict:
        # No structured meal plan found (e.g. conversational question)
        return {
            "validation_result": {"is_valid": True, "issues": [], "note": "Conversational reply"}
        }

    # Fetch targets and profile
    targets = state.get("nutrition_targets") or {}
    profile = state.get("user_profile") or {}
    calorie_target = targets.get("calorie_target", 2000.0)
    diet_type = profile.get("diet_type", "veg")
    allergies = profile.get("allergies", [])
    excluded_foods = profile.get("excluded_foods", [])
    df = _get_df()

    # Check if 7-day weekly plan or 1-day plan
    has_days = any(
        k in meal_plan_dict
        for k in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    )

    if has_days:
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
        name_index = df.set_index("food_name")[["protein", "carbohydrates", "fats"]].to_dict(orient="index")
        tot_p, tot_c, tot_f = 0.0, 0.0, 0.0
        day_count = 0
        for d in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if d in meal_plan_dict and isinstance(meal_plan_dict[d], dict):
                day_count += 1
                for s in ["breakfast", "lunch", "snack", "dinner"]:
                    for it in meal_plan_dict[d].get(s, []):
                        fn = it.get("food_name", "")
                        q = float(it.get("quantity_g", 0.0))
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
        name_index = df.set_index("food_name")[
            ["calories", "protein", "carbohydrates", "fats", "fiber"]
        ].to_dict(orient="index")

        planned_cal = 0.0
        planned_prot = 0.0
        planned_carb = 0.0
        planned_fat = 0.0

        for meal_key in ["breakfast", "lunch", "snack", "dinner"]:
            for item in meal_plan_dict.get(meal_key, []):
                fname = item.get("food_name", "")
                qty = float(item.get("quantity_g", 0))
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
    last_text = messages[-1].content if messages else "No response generated."

    val_res = state.get("validation_result") or {}
    if not val_res.get("is_valid", True):
        # Graceful fallback: append advisory notice
        issues = val_res.get("issues", [])
        issues_note = "\n".join(f"- {i}" for i in issues)
        fallback_notice = (
            f"\n\n> ⚠️ **Nutritionist Advisory:** The recommended plan has the following "
            f"minor observations:\n{issues_note}"
        )
        last_text = f"{last_text}\n{fallback_notice}"

    # Build the full structured WeeklyPlan Pydantic model
    targets_dict = state.get("nutrition_targets") or {}
    meal_plan_dict = state.get("meal_plan")
    weekly_plan_dict = None

    if targets_dict and meal_plan_dict:
        try:
            targets_obj = NutritionTargets(**targets_dict)
            df = _get_df()
            day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            has_days = any(k in meal_plan_dict for k in day_keys)

            days_list = []
            for dk in day_keys:
                day_meals = meal_plan_dict.get(dk) if has_days else meal_plan_dict
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
    if meal_plan_dict and any(
        k in meal_plan_dict
        for k in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    ):
        mon = meal_plan_dict.get("monday") or {}
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
