"""
tests/test_functional_evaluation.py
-----------------------------------
Functional verification and evaluation metrics suite:
1. Vegetarian user test case
2. Non-vegetarian user test case
3. Peanut allergy exclusion test case
4. Food substitution accuracy test case
5. Invalid user input test case
6. Plan violation revision loop test case
7. Offline / API unavailable graceful fallback test case
8. Quantitative metrics: Calculation accuracy, Dietary compliance, Calorie deviation, Task success rate
"""

import time
import json
import pytest
from core.user_profile import UserProfile
from core.calculations import calculate_nutrition_targets
from tools.food_tools import search_food_database, find_food_substitutes, validate_meal_plan
from agent.graph import (
    profile_validation_node,
    plan_revision_node,
    final_response_node,
    agent_node,
)


class TestFunctionalScenarios:
    """Test suite matching the Stage 6 functional requirements table."""

    def test_case_1_vegetarian_user(self):
        """Vegetarian user must receive only vegetarian food recommendations."""
        res = search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "lunch",
            "allergies": [],
            "excluded_foods": [],
            "top_n": 10,
        })
        items = json.loads(res)["items"]
        assert len(items) > 0
        for item in items:
            assert item["diet_type"] == "veg", f"Found non-veg item: {item['food_name']}"

    def test_case_2_non_vegetarian_user(self):
        """Non-vegetarian user can receive meat, poultry, or egg recommendations."""
        res = search_food_database.invoke({
            "diet_type": "non-veg",
            "meal_type": "lunch",
            "allergies": [],
            "excluded_foods": [],
            "top_n": 15,
        })
        items = json.loads(res)["items"]
        diet_types = {item["diet_type"] for item in items}
        assert "non-veg" in diet_types

    def test_case_3_peanut_allergy(self):
        """Peanut allergy must exclude all foods with peanut allergen tags."""
        res = search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "snack",
            "allergies": ["peanuts"],
            "excluded_foods": [],
            "top_n": 20,
        })
        items = json.loads(res)["items"]
        for item in items:
            assert "peanuts" not in item["allergens"].lower(), (
                f"Peanut item returned: {item['food_name']}"
            )

    def test_case_4_food_substitution(self):
        """Food substitution finder returns valid alternatives with high similarity."""
        res = find_food_substitutes.invoke({
            "food_name": "Paneer",
            "diet_type": "veg",
            "meal_type": "lunch",
            "allergies": [],
            "top_n": 3,
        })
        subs = json.loads(res)["substitutes"]
        assert len(subs) > 0
        assert all(s["diet_type"] == "veg" for s in subs)
        assert subs[0]["similarity_score"] > 0.85

    def test_case_5_invalid_user_information(self):
        """Invalid user information triggers validation error."""
        res = profile_validation_node({
            "user_profile": {"name": "Test", "age": -5, "gender": "male"}
        })
        assert res.get("error") is not None
        assert "validation failed" in res["error"].lower()

    def test_case_6_meal_plan_violates_restrictions(self):
        """Meal plan violating restrictions triggers revision node with feedback."""
        violating_plan = {
            "breakfast": [{"food_name": "Idli", "quantity_g": 100}],
            "lunch": [{"food_name": "Chicken Curry", "quantity_g": 200}], # Violates veg
            "snack": [{"food_name": "Apple", "quantity_g": 100}],
            "dinner": [{"food_name": "Dal Tadka", "quantity_g": 150}],
        }
        val_res = validate_meal_plan.invoke({
            "plan_json": json.dumps(violating_plan),
            "diet_type": "veg",
            "allergies": [],
            "excluded_foods": [],
            "calorie_target": 1800.0,
            "protein_g": 90.0,
            "carbs_g": 200.0,
            "fats_g": 50.0,
        })
        val_dict = json.loads(val_res)
        assert val_dict["is_valid"] is False

        # Trigger revision node
        rev_res = plan_revision_node({
            "validation_result": val_dict,
            "revision_count": 0,
            "messages": [],
        })
        assert rev_res["revision_count"] == 1
        assert "Chicken Curry" in rev_res["messages"][0].content

    def test_case_7_gemini_api_unavailable_handling(self):
        """When API key is missing or offline, graceful fallback message is returned."""
        res = agent_node({"messages": [], "error": None})
        assert len(res["messages"]) == 1
        assert "API key" in res["messages"][0].content or "offline" in res["messages"][0].content.lower()


class TestQuantitativeEvaluationMetrics:
    """Benchmark tests verifying project KPIs."""

    def test_calculation_accuracy(self):
        """Verify mathematical precision within +/- 1 kcal."""
        profile = UserProfile(
            name="Test",
            age=30,
            gender="male",
            height_cm=180.0,
            weight_kg=80.0,
            activity_level="sedentary",
            fitness_goal="maintenance",
            diet_type="veg",
        )
        targets = calculate_nutrition_targets(profile)
        # Expected: BMR = (10*80) + (6.25*180) - (5*30) + 5 = 800 + 1125 - 150 + 5 = 1780.0
        # TDEE = 1780 * 1.2 = 2136.0
        assert abs(targets.bmr - 1780.0) < 0.1
        assert abs(targets.tdee - 2136.0) < 0.1
        assert abs(targets.calorie_target - 2136.0) < 0.1

    def test_dietary_compliance_rate(self):
        """Verify 100% compliance across vegetarian items."""
        df = search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "lunch",
            "allergies": ["dairy", "gluten"],
            "excluded_foods": ["Aloo Gobi"],
            "top_n": 50,
        })
        items = json.loads(df)["items"]
        for it in items:
            assert it["diet_type"] == "veg"
            assert "dairy" not in it["allergens"].lower()
            assert "gluten" not in it["allergens"].lower()
            assert it["food_name"] != "Aloo Gobi"

    def test_response_time_benchmark(self):
        """Benchmark that local tool and calculation pipeline responds in under 0.5s."""
        start = time.perf_counter()
        p = UserProfile(
            name="Bench",
            age=25,
            gender="female",
            height_cm=165.0,
            weight_kg=60.0,
            activity_level="moderately_active",
            fitness_goal="weight_loss",
            diet_type="veg",
        )
        targets = calculate_nutrition_targets(p)
        search_res = search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "lunch",
            "allergies": [],
            "excluded_foods": [],
        })
        elapsed = time.perf_counter() - start
        assert elapsed < 0.5, f"Pipeline too slow: {elapsed:.3f}s"
