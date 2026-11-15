"""
tests/test_tools.py
-------------------
Unit tests for the 5 Python Tools:
1. calculate_nutrition_targets
2. search_food_database
3. calculate_meal_nutrition
4. find_food_substitutes
5. validate_meal_plan
"""

import json
import pytest
from tools.nutrition_tools import calculate_nutrition_targets
from tools.food_tools import (
    search_food_database,
    calculate_meal_nutrition,
    find_food_substitutes,
    validate_meal_plan,
)


class TestTool1NutritionTargets:
    def test_calculate_targets_valid(self):
        res = calculate_nutrition_targets.invoke({
            "name": "Kavita",
            "age": 29,
            "gender": "female",
            "height_cm": 160.0,
            "weight_kg": 60.0,
            "activity_level": "moderately_active",
            "fitness_goal": "weight_loss",
            "diet_type": "veg",
            "allergies": [],
            "excluded_foods": [],
        })
        data = json.loads(res)
        assert "error" not in data
        assert data["bmi"] == 23.44
        assert data["bmi_category"] == "Normal weight"
        assert data["calorie_target"] > 1200.0
        assert data["protein_g"] == 108.0  # 60 * 1.8


class TestTool2FoodSearch:
    def test_search_veg_breakfast(self):
        res = search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "breakfast",
            "allergies": [],
            "excluded_foods": [],
        })
        data = json.loads(res)
        assert data["count"] > 0
        for item in data["items"]:
            assert item["diet_type"] == "veg"
            assert "breakfast" in item["meal_type"]

    def test_search_allergen_exclusion(self):
        res = search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "lunch",
            "allergies": ["dairy"],
            "excluded_foods": [],
        })
        data = json.loads(res)
        for item in data["items"]:
            assert "dairy" not in item["allergens"].lower()

    def test_search_excluded_foods(self):
        res = search_food_database.invoke({
            "diet_type": "veg",
            "meal_type": "snack",
            "allergies": [],
            "excluded_foods": ["Samosa"],
        })
        data = json.loads(res)
        names = [item["food_name"] for item in data["items"]]
        assert "Samosa" not in names


class TestTool3MealNutrition:
    def test_calculate_meal_nutrition_valid(self):
        items = [
            {"food_name": "Idli", "quantity_g": 100},
            {"food_name": "Sambar", "quantity_g": 100},
        ]
        res = calculate_meal_nutrition.invoke({"items_json": json.dumps(items)})
        data = json.loads(res)
        assert "error" not in data
        assert data["total_calories"] == 128.0  # 58 + 70
        assert len(data["breakdown"]) == 2

    def test_unknown_food_returns_error(self):
        items = [{"food_name": "NonExistentDish123", "quantity_g": 100}]
        res = calculate_meal_nutrition.invoke({"items_json": json.dumps(items)})
        data = json.loads(res)
        assert "error" in data


class TestTool4Substitutes:
    def test_find_substitutes_veg(self):
        res = find_food_substitutes.invoke({
            "food_name": "Paneer",
            "diet_type": "veg",
            "meal_type": "lunch",
            "allergies": [],
            "top_n": 3,
        })
        data = json.loads(res)
        assert len(data["substitutes"]) > 0
        for sub in data["substitutes"]:
            assert sub["diet_type"] == "veg"
            assert sub["food_name"] != "Paneer"
            assert 0.0 <= sub["similarity_score"] <= 1.0


class TestTool5MealPlanValidator:
    def test_valid_plan_passes(self):
        plan = {
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
                {"food_name": "Whole Wheat Roti", "quantity_g": 90},
            ],
        }
        res = validate_meal_plan.invoke({
            "plan_json": json.dumps(plan),
            "diet_type": "veg",
            "allergies": [],
            "excluded_foods": [],
            "calorie_target": 1400.0,
            "protein_g": 60.0,
            "carbs_g": 180.0,
            "fats_g": 40.0,
        })
        data = json.loads(res)
        assert data["is_valid"] is True
        assert len(data["issues"]) == 0

    def test_diet_violation_caught(self):
        plan = {
            "breakfast": [{"food_name": "Idli", "quantity_g": 150}],
            "lunch": [{"food_name": "Chicken Curry", "quantity_g": 150}],
            "snack": [{"food_name": "Apple", "quantity_g": 100}],
            "dinner": [{"food_name": "Dal Tadka", "quantity_g": 150}],
        }
        res = validate_meal_plan.invoke({
            "plan_json": json.dumps(plan),
            "diet_type": "veg",
            "allergies": [],
            "excluded_foods": [],
            "calorie_target": 1500.0,
            "protein_g": 80.0,
            "carbs_g": 180.0,
            "fats_g": 45.0,
        })
        data = json.loads(res)
        assert data["is_valid"] is False
        assert any("vegetarian" in i.lower() for i in data["issues"])

    def test_allergen_violation_caught(self):
        plan = {
            "breakfast": [{"food_name": "Poha", "quantity_g": 150}],  # Contains peanuts
            "lunch": [{"food_name": "Dal Tadka", "quantity_g": 150}],
            "snack": [{"food_name": "Apple", "quantity_g": 100}],
            "dinner": [{"food_name": "Dal Tadka", "quantity_g": 150}],
        }
        res = validate_meal_plan.invoke({
            "plan_json": json.dumps(plan),
            "diet_type": "veg",
            "allergies": ["peanuts"],
            "excluded_foods": [],
            "calorie_target": 1000.0,
            "protein_g": 40.0,
            "carbs_g": 120.0,
            "fats_g": 30.0,
        })
        data = json.loads(res)
        assert data["is_valid"] is False
        assert any("peanuts" in i.lower() for i in data["issues"])
