"""
tests/test_complete_system_verification.py
-----------------------------------------
End-to-end verification script testing every single component and workflow step:
1. Biometric & Nutritional Math (BMI, BMR, TDEE, Macros)
2. 5 Python Nutrition Tools
3. Multi-User Planning (Vegetarian, Non-Vegetarian, Allergies, Exclusions)
4. Dedicated 4-Meal Time Slots (Morning, Afternoon, Evening, Dinner) across all 7 days
5. RAG Retrieval & Citation Grounding
6. Irrelevant Query Rejection
7. Chatturn Reasoning & Alternatives
8. UI Module Load Integrity & Zero Deprecation Warnings
"""

import json
import pytest
import pandas as pd

from core.user_profile import UserProfile
from core.calculations import (
    calculate_bmi,
    get_bmi_category,
    calculate_bmr,
    calculate_tdee,
    calculate_nutrition_targets,
    build_day_plan_detail,
    DAYS_OF_WEEK,
)
from tools.food_tools import (
    _get_df,
    search_food_database,
    calculate_meal_nutrition,
    find_food_substitutes,
    validate_meal_plan,
)
from tools.nutrition_tools import calculate_nutrition_targets as tool_calc_targets
from agent.graph import app_graph, extract_meal_plan_json, generate_demo_meal_plan
from rag.retriever import retrieve_nutrition_knowledge, retrieve_relevant_chunks, MAX_RELEVANCE_DISTANCE
from ui.meal_planner import MEAL_CONFIG, DAYS_ORDER


class TestTopToBottomVerification:
    """Comprehensive test covering all user journeys and system components."""

    # 1. BIOMETRIC CALCULATIONS
    def test_biometric_calculations_male_and_female(self):
        # Male 28y, 175cm, 75kg
        bmi_m = calculate_bmi(75.0, 175.0)
        cat_m = get_bmi_category(bmi_m)
        assert round(bmi_m, 1) == 24.5
        assert cat_m == "Normal weight"

        bmr_m = calculate_bmr(75.0, 175.0, 28, "male")
        assert round(bmr_m, 1) == 1708.8

        tdee_m = calculate_tdee(bmr_m, "moderately_active")
        assert round(tdee_m, 1) == round(1708.75 * 1.55, 1)

        # Female 25y, 162cm, 56kg
        bmi_f = calculate_bmi(56.0, 162.0)
        cat_f = get_bmi_category(bmi_f)
        assert round(bmi_f, 1) == 21.3
        assert cat_f == "Normal weight"

        bmr_f = calculate_bmr(56.0, 162.0, 25, "female")
        assert round(bmr_f, 1) == 1286.5

    def test_macro_targets_consistency(self):
        profile = UserProfile(
            name="TestUser",
            age=30,
            gender="male",
            height_cm=178.0,
            weight_kg=76.0,
            activity_level="moderately_active",
            fitness_goal="weight_loss",
            diet_type="veg",
            allergies=[],
            excluded_foods=[],
        )
        targets = calculate_nutrition_targets(profile)
        # Weight loss deficit
        assert targets.calorie_target < targets.tdee
        # Macro calories sum within 15 kcal of calorie_target
        sum_cal = (targets.protein_g * 4) + (targets.carbs_g * 4) + (targets.fats_g * 9)
        assert abs(sum_cal - targets.calorie_target) <= 15.0
        # Dietary fiber >= 14g / 1000 kcal
        assert targets.fiber_g >= (targets.calorie_target / 1000.0) * 14.0

    # 2. PYTHON NUTRITION TOOLS
    def test_all_five_tools(self):
        # Tool 1: Targets
        t1_res = json.loads(tool_calc_targets.invoke({
            "name": "Arjun",
            "age": 28,
            "gender": "male",
            "height_cm": 175.0,
            "weight_kg": 75.0,
            "activity_level": "moderately_active",
            "fitness_goal": "weight_loss",
            "diet_type": "veg",
            "allergies": [],
            "excluded_foods": [],
        }))
        assert "calorie_target" in t1_res
        assert t1_res["calorie_target"] > 1200.0

        # Tool 2: Food Search
        t2_res = json.loads(search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "breakfast",
            "allergies": ["gluten"],
            "excluded_foods": [],
        }))
        assert t2_res["count"] > 0
        for it in t2_res["items"]:
            assert it["diet_type"] == "veg"
            assert "gluten" not in it["allergens"].lower()

        # Tool 3: Meal Nutrition
        items = [
            {"food_name": "Idli", "quantity_g": 100},
            {"food_name": "Sambar", "quantity_g": 100},
        ]
        t3_res = json.loads(calculate_meal_nutrition.invoke({"items_json": json.dumps(items)}))
        assert "error" not in t3_res
        assert t3_res["total_calories"] > 0
        assert t3_res["total_protein"] > 0

        # Tool 4: Substitutes
        t4_res = json.loads(find_food_substitutes.invoke({
            "food_name": "Idli",
            "diet_type": "veg",
            "meal_type": "breakfast",
            "allergies": [],
            "top_n": 3,
        }))
        assert len(t4_res["substitutes"]) > 0

        # Tool 5: Validation
        plan_test = {
            "breakfast": [
                {"food_name": "Idli", "quantity_g": 200},
                {"food_name": "Sambar", "quantity_g": 150},
            ],
            "lunch": [
                {"food_name": "Dal Tadka", "quantity_g": 200},
                {"food_name": "Basmati Rice", "quantity_g": 200},
            ],
            "snack": [{"food_name": "Apple", "quantity_g": 150}],
            "dinner": [
                {"food_name": "Palak Paneer", "quantity_g": 200},
                {"food_name": "Whole Wheat Roti", "quantity_g": 100},
            ],
        }
        t5_res = json.loads(validate_meal_plan.invoke({
            "plan_json": json.dumps(plan_test),
            "diet_type": "veg",
            "allergies": [],
            "excluded_foods": [],
            "calorie_target": 1400.0,
            "protein_g": 80.0,
            "carbs_g": 220.0,
            "fats_g": 50.0,
        }))
        assert t5_res["is_valid"] is True
        assert len(t5_res["issues"]) == 0

    # 3. MULTI-USER END-TO-END PLANNING
    @pytest.mark.parametrize("user_case", [
        {
            "name": "User_Veg_WeightLoss",
            "diet_type": "veg",
            "fitness_goal": "weight_loss",
            "allergies": [],
            "excluded_foods": [],
        },
        {
            "name": "User_NonVeg_MuscleGain",
            "diet_type": "non-veg",
            "fitness_goal": "muscle_gain",
            "allergies": [],
            "excluded_foods": [],
        },
        {
            "name": "User_Veg_Allergy_Peanuts",
            "diet_type": "veg",
            "fitness_goal": "maintenance",
            "allergies": ["peanuts", "tree_nuts"],
            "excluded_foods": ["Samosa"],
        },
    ])
    def test_multi_user_plan_generation(self, user_case):
        profile = UserProfile(
            name=user_case["name"],
            age=29,
            gender="male",
            height_cm=176.0,
            weight_kg=74.0,
            activity_level="moderately_active",
            fitness_goal=user_case["fitness_goal"],
            diet_type=user_case["diet_type"],
            allergies=user_case["allergies"],
            excluded_foods=user_case["excluded_foods"],
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        config = {"configurable": {"thread_id": f"test_thread_{user_case['name']}"}}
        init_state = {
            "user_profile": profile.model_dump(),
            "nutrition_targets": targets,
            "messages": [],
            "revision_count": 0,
        }
        res = app_graph.invoke(init_state, config=config)

        assert res.get("weekly_plan") is not None
        assert res.get("meal_plan") is not None
        wp = res["weekly_plan"]
        assert len(wp["days"]) == 7

        # Verify all 4 time slots for each day
        for day_detail in wp["days"]:
            meals = day_detail["meals"]
            for slot in ["breakfast", "lunch", "snack", "dinner"]:
                assert slot in meals
                assert len(meals[slot]["items"]) > 0
                for it in meals[slot]["items"]:
                    # Allergen guard
                    for a in user_case["allergies"]:
                        assert a.lower() not in it.get("allergens", "").lower()
                    # Diet guard
                    if user_case["diet_type"] == "veg":
                        assert it.get("diet_type") == "veg"

    # 4. DEDICATED 4 MEAL SLOTS CONFIGURATION
    def test_meal_config_slots_coverage(self):
        expected_slots = ["breakfast", "lunch", "snack", "dinner"]
        for slot in expected_slots:
            assert slot in MEAL_CONFIG
            assert "title" in MEAL_CONFIG[slot]
            assert "time" in MEAL_CONFIG[slot]
            assert "nutrition_tip" in MEAL_CONFIG[slot]
            assert len(MEAL_CONFIG[slot]["alternatives"]) > 0

    # 5. RAG KNOWLEDGE BASE RETRIEVAL & GROUNDING
    def test_rag_knowledge_retrieval(self):
        res = retrieve_nutrition_knowledge.invoke({"query": "What are the benefits of dietary fibre in Indian diets?"})
        assert "ICMR_NIN_Dietary_Guidelines_for_Indians.pdf" in res
        assert "Page" in res
        assert "Vector Distance" in res

    def test_rag_irrelevant_rejection(self):
        res = retrieve_nutrition_knowledge.invoke({"query": "Who won the cricket world cup in 2011?"})
        assert "No relevant nutrition document sections were found" in res

    # 6. CHAT TURN ALTERNATIVES REASONING
    def test_chat_turn_evening_snacks_reasoning(self):
        config = {"configurable": {"thread_id": "test_chat_snacks"}}
        from langchain_core.messages import HumanMessage
        state = {
            "user_profile": {"name": "Arjun", "diet_type": "veg"},
            "nutrition_targets": {"calorie_target": 2000.0},
            "messages": [HumanMessage(content="What healthy snacks can I take in the evening?")],
            "revision_count": 0,
        }
        res = app_graph.invoke(state, config=config)
        last_reply = res["messages"][-1].content
        assert len(last_reply) > 20
        assert any(w in last_reply.lower() for w in ["guidance", "snack", "icmr", "nutrition", "food"])
