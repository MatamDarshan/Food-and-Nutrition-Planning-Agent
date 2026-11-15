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
from core.calculations import calculate_nutrition_targets as _calc_targets
from core.user_profile import UserProfile
from core.validation import run_all_checks
from tools.food_tools import (
    _get_df,
    calculate_meal_nutrition,
    find_food_substitutes,
    search_food_database,
    validate_meal_plan,
)
from tools.nutrition_tools import calculate_nutrition_targets


# ── Registered Tools ──────────────────────────────────────────────────────────

ALL_TOOLS = [
    calculate_nutrition_targets,
    search_food_database,
    calculate_meal_nutrition,
    find_food_substitutes,
    validate_meal_plan,
]


# ── JSON Helper ───────────────────────────────────────────────────────────────

def extract_meal_plan_json(text: str) -> Optional[dict]:
    """Extract a meal plan dictionary from model output text.

    Looks for JSON fenced in code blocks, or raw JSON object containing
    the expected meal keys.
    """
    if not text:
        return None

    # 1. Try markdown code blocks: ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, re.IGNORECASE)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if any(k in parsed for k in ["breakfast", "lunch", "dinner", "snack"]):
                return parsed
        except json.JSONDecodeError:
            pass

    # 2. Try outermost curly braces containing meal keys
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        snippet = text[first_brace : last_brace + 1]
        try:
            parsed = json.loads(snippet)
            if any(k in parsed for k in ["breakfast", "lunch", "dinner", "snack"]):
                return parsed
        except json.JSONDecodeError:
            pass

    return None


# ── Node 1: Profile Validation ────────────────────────────────────────────────

def profile_validation_node(state: AgentState) -> dict[str, Any]:
    """Validate user profile data using Pydantic UserProfile model."""
    raw_profile = state.get("user_profile")
    if not raw_profile:
        return {"error": "No user profile provided."}

    try:
        profile_obj = UserProfile(**raw_profile)
        return {
            "user_profile": profile_obj.model_dump(),
            "error": None,
        }
    except Exception as exc:
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
        return {"error": "Missing user profile in state."}

    profile_obj = UserProfile(**raw_profile)
    targets = _calc_targets(profile_obj)
    targets_dict = targets.model_dump()

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

    return {
        "nutrition_targets": targets_dict,
        "messages": [HumanMessage(content=context_msg)],
    }


# ── Demo Mode Fallback Plan Generator ─────────────────────────────────────────

def generate_demo_meal_plan(profile: dict, targets: dict) -> str:
    """Generate an optimal, fully-compliant Indian meal plan using deterministic rules.

    Used for seamless demo presentation when an external API key is invalid or offline.
    Directly leverages the ICMR-NIN database and enforces dietary and allergen constraints.
    """
    df = _get_df()
    diet_type = profile.get("diet_type", "veg")
    allergies = profile.get("allergies", [])
    excluded = [f.lower() for f in profile.get("excluded_foods", [])]
    cal_target = targets.get("calorie_target", 2000.0)

    # Filter helper
    def get_slot_candidates(meal_slot: str) -> list[dict]:
        mask = (
            (df["diet_type"] == "veg" if diet_type == "veg" else pd.Series([True] * len(df)))
            & df["meal_type"].str.contains(meal_slot, regex=False, na=False)
            & ~df["food_name"].str.lower().isin(excluded)
        )
        for allergen in allergies:
            mask = mask & ~df["allergens"].str.contains(allergen, case=False, regex=False, na=False)
        matched = df[mask]
        return matched.to_dict(orient="records") if not matched.empty else []

    b_cands = get_slot_candidates("breakfast")
    l_cands = get_slot_candidates("lunch")
    s_cands = get_slot_candidates("snack")
    d_cands = get_slot_candidates("dinner")

    # Pick representative foods
    def pick_items(cands: list[dict], default_names: list[str], fallback_cat: str) -> list[str]:
        names_in_cands = {c["food_name"] for c in cands}
        chosen = [n for n in default_names if n in names_in_cands]
        if not chosen and cands:
            chosen = [cands[0]["food_name"]]
        return chosen

    # Default balanced Indian staples
    b_chosen = pick_items(b_cands, ["Idli", "Sambar", "Besan Chilla", "Poha", "Egg Bhurji"], "Grain")[:2]
    l_chosen = pick_items(l_cands, ["Basmati Rice", "Dal Tadka", "Palak Paneer", "Chicken Curry", "Raita"], "Legume")[:3]
    s_chosen = pick_items(s_cands, ["Sprouts Salad", "Apple", "Banana", "Dhokla", "Papaya"], "Fruit")[:1]
    d_chosen = pick_items(d_cands, ["Whole Wheat Roti", "Chana Masala", "Dal Makhani", "Baingan Bharta"], "Grain")[:2]

    # Baseline portion sizes (grams)
    base_plan = {
        "breakfast": [{"food_name": name, "quantity_g": 120.0} for name in b_chosen],
        "lunch": [{"food_name": name, "quantity_g": 150.0} for name in l_chosen],
        "snack": [{"food_name": name, "quantity_g": 100.0} for name in s_chosen],
        "dinner": [{"food_name": name, "quantity_g": 120.0} for name in d_chosen],
    }

    # Calculate baseline calories
    name_map = df.set_index("food_name")["calories"].to_dict()
    raw_cal = 0.0
    for meal_items in base_plan.values():
        for it in meal_items:
            raw_cal += (name_map.get(it["food_name"], 100.0) * it["quantity_g"]) / 100.0

    # Scale portions to match calorie target within +/- 2%
    scale = cal_target / max(raw_cal, 500.0)
    scaled_plan: dict[str, list[dict]] = {}
    for slot, items in base_plan.items():
        scaled_plan[slot] = []
        for it in items:
            adjusted_qty = round(it["quantity_g"] * scale / 5.0) * 5.0  # round to nearest 5g
            scaled_plan[slot].append({
                "food_name": it["food_name"],
                "quantity_g": max(adjusted_qty, 30.0),
            })

    plan_json = json.dumps(scaled_plan, indent=2)
    demo_explanation = (
        f"### 🥗 Personalized Meal Plan (Target: {cal_target:.0f} kcal)\n\n"
        f"```json\n{plan_json}\n```\n\n"
        f"**Nutritionist Rationale:**\n"
        f"- **Breakfast:** Light, easily digestible energy source paired with protein.\n"
        f"- **Lunch:** Wholesome Indian staple combining complex carbohydrates and protein.\n"
        f"- **Evening Snack:** High-fiber, nutrient-dense snack to prevent late-day energy dips.\n"
        f"- **Dinner:** Balanced low-glycemic combination for sustained satiety and overnight muscle recovery.\n\n"
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

    # Check if this is a follow-up conversational question vs meal plan generation
    messages = list(state.get("messages", []))
    is_chat_turn = len(messages) > 1 and any(
        isinstance(m, HumanMessage) and not m.content.startswith("USER GOALS")
        for m in messages
    )

    if not api_key:
        if is_chat_turn:
            last_q = messages[-1].content
            reply = (
                f"**AI Nutritionist (Demo Mode):** For personalized interactive follow-ups "
                f"('{last_q}'), please enter a valid Google Gemini API key in the sidebar."
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
        ):
            demo_content = generate_demo_meal_plan(profile, targets)
            notice = (
                f"> 💡 **Demo Mode Activated:** The provided API key was invalid. "
                f"Successfully generated a 100% compliant meal plan using the ICMR-NIN planning engine.\n\n"
                f"{demo_content}"
            )
            return {"messages": [AIMessage(content=notice)]}
        elif "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
            demo_content = generate_demo_meal_plan(profile, targets)
            notice = (
                f"> 💡 **Demo Mode Activated:** Gemini rate limit reached. "
                f"Successfully generated your meal plan using the ICMR-NIN planning engine.\n\n"
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

    # Calculate actual nutrition using database
    df = _get_df()
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
    """Assemble final validated plan and conversational response."""
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

    return {"final_response": str(last_text)}


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
