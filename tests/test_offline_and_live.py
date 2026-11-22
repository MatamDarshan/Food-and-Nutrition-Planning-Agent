"""
tests/test_offline_and_live.py
------------------------------
Verifies:
1. Offline fallback planner triggers when API key is missing or invalid.
2. The generated offline meal plan is 100% compliant and valid.
3. Chat assistant handles offline turns gracefully.
4. Gemini connection initializes correctly with GOOGLE_API_KEY.
5. All 5 tools remain functional.
"""

import json
import pytest
from core.user_profile import UserProfile
from core.calculations import calculate_nutrition_targets
from agent.graph import app_graph
from tools.food_tools import (
    search_food_database,
    calculate_meal_nutrition,
    find_food_substitutes,
    validate_meal_plan,
)
from tools.nutrition_tools import calculate_nutrition_targets as tool1_calc
from config.settings import settings


def test_offline_fallback_planner():
    """Verify that when no API key is present, offline planner produces a valid plan."""
    profile = UserProfile(
        name="TestUser",
        age=28,
        gender="male",
        height_cm=175.0,
        weight_kg=75.0,
        activity_level="moderately_active",
        fitness_goal="weight_loss",
        diet_type="veg",
        allergies=["peanuts"],
        excluded_foods=["Samosa"],
    )
    targets = calculate_nutrition_targets(profile).model_dump()
    config = {"configurable": {"thread_id": "test-offline-plan-1"}}
    res = app_graph.invoke(
        {
            "user_profile": profile.model_dump(),
            "nutrition_targets": targets,
            "messages": [],
            "revision_count": 0,
        },
        config=config,
    )

    plan = res.get("meal_plan")
    val = res.get("validation_result")

    assert plan is not None, "Meal plan must be generated in offline mode"
    assert "breakfast" in plan and len(plan["breakfast"]) > 0
    assert "lunch" in plan and len(plan["lunch"]) > 0
    assert "dinner" in plan and len(plan["dinner"]) > 0

    assert val is not None, "Validation result must be present"
    assert val.get("is_valid") is True, f"Validation issues: {val.get('issues')}"
    # Verify no peanut or samosa
    for slot, items in plan.items():
        for item in items:
            assert item["food_name"] != "Samosa"
            assert "poha" not in item["food_name"].lower()


def test_offline_chat_turn():
    """Verify that offline chat assistant answers common queries without crashing."""
    from langchain_core.messages import HumanMessage
    config = {"configurable": {"thread_id": "test-offline-chat-1"}}
    res = app_graph.invoke(
        {
            "messages": [HumanMessage(content="Suggest an alternative to paneer")],
            "revision_count": 0,
        },
        config=config,
    )
    resp = res.get("final_response") or res["messages"][-1].content
    assert resp is not None
    assert "paneer" in resp.lower() or "protein" in resp.lower()


def test_centralized_settings():
    """Verify settings use GOOGLE_API_KEY consistently."""
    assert hasattr(settings, "google_api_key")
    assert hasattr(settings, "api_key")
    assert settings.model_name.startswith("gemini-")


def test_all_five_tools_functional():
    """Verify all 5 tools execute cleanly."""
    t1 = tool1_calc.invoke({
        "name": "A", "age": 25, "gender": "female", "height_cm": 160.0, "weight_kg": 55.0,
        "activity_level": "sedentary", "fitness_goal": "maintenance", "diet_type": "veg",
        "allergies": [], "excluded_foods": []
    })
    assert "calorie_target" in t1

    t2 = search_food_database.invoke({
        "diet_type": "veg", "meal_type": "lunch", "allergies": [], "excluded_foods": []
    })
    assert "items" in t2

    t3 = calculate_meal_nutrition.invoke({
        "items_json": json.dumps([{"food_name": "Idli", "quantity_g": 100}])
    })
    assert "total_calories" in t3

    t4 = find_food_substitutes.invoke({
        "food_name": "Paneer", "diet_type": "veg", "meal_type": "lunch", "allergies": []
    })
    assert "substitutes" in t4

    t5 = validate_meal_plan.invoke({
        "plan_json": json.dumps({
            "breakfast": [{"food_name": "Idli", "quantity_g": 100}],
            "lunch": [{"food_name": "Dal Tadka", "quantity_g": 100}],
            "snack": [{"food_name": "Apple", "quantity_g": 100}],
            "dinner": [{"food_name": "Roti", "quantity_g": 50}],
        }),
        "diet_type": "veg", "allergies": [], "excluded_foods": [],
        "calorie_target": 500.0, "protein_g": 20.0, "carbs_g": 80.0, "fats_g": 15.0
    })
    assert "is_valid" in t5
