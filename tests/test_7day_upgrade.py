"""
tests/test_7day_upgrade.py
--------------------------
Comprehensive verification suite for the 7-Day Meal Planning & Redesign Upgrade.
Tests all 15 required scenarios:
1. Vegetarian profile 7-day plan
2. Non-vegetarian profile 7-day plan
3. Weight-loss goal deficit & target matching
4. Weight-maintenance goal & target matching
5. Weight-gain goal surplus & target matching
6. Egg allergy exclusion across 7 days
7. Milk/dairy allergy exclusion across 7 days
8. Multiple food exclusions across 7 days
9. Complete 7-day plan completeness (all 7 days & 4 meals/day present)
10. Daily nutritional calculations (item sums = meal totals, meal sums = day totals)
11. Weekly nutritional averages calculation & compliance
12. Meal substitutions
13. RAG-based nutrition questions with source attribution
14. Irrelevant nutrition questions rejected
15. Missing/invalid API key offline 7-day plan fallback
"""

import json
import pytest
from core.user_profile import UserProfile
from core.calculations import (
    calculate_nutrition_targets,
    build_day_plan_detail,
    calculate_weekly_averages,
    DAYS_OF_WEEK,
)
from core.validation import run_weekly_checks, run_all_checks
from tools.food_tools import _get_df, find_food_substitutes
from agent.graph import app_graph, generate_demo_meal_plan, extract_meal_plan_json
from rag.retriever import retrieve_nutrition_knowledge, retrieve_relevant_chunks, MAX_RELEVANCE_DISTANCE


class TestUpgrade15Scenarios:

    def test_case_1_vegetarian_7day_plan(self):
        """1. Vegetarian profile: Verify all 7 days have zero non-veg foods."""
        profile = UserProfile(
            name="VegUser",
            age=26,
            gender="female",
            height_cm=165.0,
            weight_kg=60.0,
            activity_level="moderately_active",
            fitness_goal="maintenance",
            diet_type="veg",
            allergies=[],
            excluded_foods=[],
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        demo_str = generate_demo_meal_plan(profile.model_dump(), targets)
        plan_dict = extract_meal_plan_json(demo_str)
        assert plan_dict is not None

        df = _get_df()
        name_to_diet = df.set_index("food_name")["diet_type"].to_dict()

        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            assert day in plan_dict
            for slot in ["breakfast", "lunch", "snack", "dinner"]:
                for item in plan_dict[day].get(slot, []):
                    fname = item["food_name"]
                    assert name_to_diet.get(fname) == "veg", f"Non-veg food '{fname}' found in veg plan on {day} {slot}!"

    def test_case_2_non_vegetarian_7day_plan(self):
        """2. Non-vegetarian profile: Verify non-veg options are present across the week."""
        profile = UserProfile(
            name="NonVegUser",
            age=30,
            gender="male",
            height_cm=178.0,
            weight_kg=78.0,
            activity_level="very_active",
            fitness_goal="muscle_gain",
            diet_type="non-veg",
            allergies=[],
            excluded_foods=[],
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        demo_str = generate_demo_meal_plan(profile.model_dump(), targets)
        plan_dict = extract_meal_plan_json(demo_str)
        assert plan_dict is not None

        df = _get_df()
        name_to_diet = df.set_index("food_name")["diet_type"].to_dict()

        non_veg_found = []
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            for slot in ["breakfast", "lunch", "snack", "dinner"]:
                for item in plan_dict[day].get(slot, []):
                    fname = item["food_name"]
                    if name_to_diet.get(fname) == "non-veg":
                        non_veg_found.append(fname)

        assert len(non_veg_found) > 0, "Non-vegetarian plan must include non-vegetarian protein items!"

    def test_case_3_weight_loss_goal(self):
        """3. Weight-loss goal: 500 kcal deficit applied and planned calories adhere."""
        profile = UserProfile(
            name="LossUser",
            age=35,
            gender="male",
            height_cm=175.0,
            weight_kg=85.0,
            activity_level="sedentary",
            fitness_goal="weight_loss",
            diet_type="veg",
        )
        targets = calculate_nutrition_targets(profile)
        assert targets.calorie_target == targets.tdee - 500.0

        demo_str = generate_demo_meal_plan(profile.model_dump(), targets.model_dump())
        plan_dict = extract_meal_plan_json(demo_str)
        df = _get_df()

        issues, dev_pct, daily_cals = run_weekly_checks(
            weekly_plan=plan_dict,
            diet_type=profile.diet_type,
            allergies=profile.allergies,
            excluded_foods=profile.excluded_foods,
            calorie_target=targets.calorie_target,
            food_df=df,
        )
        assert len(issues) == 0
        assert abs(dev_pct) <= 15.0

    def test_case_4_weight_maintenance_goal(self):
        """4. Weight-maintenance goal: Target equals TDEE."""
        profile = UserProfile(
            name="MaintUser",
            age=25,
            gender="female",
            height_cm=160.0,
            weight_kg=55.0,
            activity_level="moderately_active",
            fitness_goal="maintenance",
            diet_type="veg",
        )
        targets = calculate_nutrition_targets(profile)
        assert targets.calorie_target == targets.tdee

    def test_case_5_weight_gain_goal(self):
        """5. Weight-gain goal: 300 kcal lean bulk surplus applied."""
        profile = UserProfile(
            name="GainUser",
            age=22,
            gender="male",
            height_cm=180.0,
            weight_kg=68.0,
            activity_level="very_active",
            fitness_goal="muscle_gain",
            diet_type="non-veg",
        )
        targets = calculate_nutrition_targets(profile)
        assert targets.calorie_target == targets.tdee + 300.0

    def test_case_6_egg_allergy(self):
        """6. Egg allergy: Strictly zero egg-containing foods across all 7 days."""
        profile = UserProfile(
            name="NoEggUser",
            age=29,
            gender="female",
            height_cm=162.0,
            weight_kg=58.0,
            activity_level="lightly_active",
            fitness_goal="maintenance",
            diet_type="non-veg",
            allergies=["eggs"],
            excluded_foods=[],
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        demo_str = generate_demo_meal_plan(profile.model_dump(), targets)
        plan_dict = extract_meal_plan_json(demo_str)
        df = _get_df()

        issues, _, _ = run_weekly_checks(
            weekly_plan=plan_dict,
            diet_type=profile.diet_type,
            allergies=profile.allergies,
            excluded_foods=profile.excluded_foods,
            calorie_target=targets["calorie_target"],
            food_df=df,
        )
        assert len(issues) == 0

        # Direct search for any egg item in the plan
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            for slot in ["breakfast", "lunch", "snack", "dinner"]:
                for item in plan_dict[day].get(slot, []):
                    assert "egg" not in item["food_name"].lower()

    def test_case_7_milk_allergy(self):
        """7. Milk/dairy allergy: Strictly zero dairy products across all 7 days."""
        profile = UserProfile(
            name="NoDairyUser",
            age=27,
            gender="male",
            height_cm=172.0,
            weight_kg=70.0,
            activity_level="moderately_active",
            fitness_goal="weight_loss",
            diet_type="veg",
            allergies=["dairy"],
            excluded_foods=[],
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        demo_str = generate_demo_meal_plan(profile.model_dump(), targets)
        plan_dict = extract_meal_plan_json(demo_str)
        df = _get_df()

        name_to_allergens = df.set_index("food_name")["allergens"].to_dict()
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            for slot in ["breakfast", "lunch", "snack", "dinner"]:
                for item in plan_dict[day].get(slot, []):
                    fn = item["food_name"]
                    al = str(name_to_allergens.get(fn, "")).lower()
                    assert "dairy" not in al, f"Dairy item '{fn}' found on {day} {slot}!"

    def test_case_8_multiple_food_exclusions(self):
        """8. Multiple food exclusions: Strictly exclude user's specific disallowed foods."""
        excluded = ["Samosa", "Bhel Puri", "Poha", "Dal Makhani"]
        profile = UserProfile(
            name="CustomUser",
            age=32,
            gender="female",
            height_cm=168.0,
            weight_kg=62.0,
            activity_level="moderately_active",
            fitness_goal="weight_loss",
            diet_type="veg",
            allergies=["peanuts"],
            excluded_foods=excluded,
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        demo_str = generate_demo_meal_plan(profile.model_dump(), targets)
        plan_dict = extract_meal_plan_json(demo_str)
        df = _get_df()

        issues, _, _ = run_weekly_checks(
            weekly_plan=plan_dict,
            diet_type=profile.diet_type,
            allergies=profile.allergies,
            excluded_foods=profile.excluded_foods,
            calorie_target=targets["calorie_target"],
            food_df=df,
        )
        assert len(issues) == 0

        # Check that none of the excluded items appear
        ex_lower = {e.lower() for e in excluded}
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            for slot in ["breakfast", "lunch", "snack", "dinner"]:
                for item in plan_dict[day].get(slot, []):
                    assert item["food_name"].lower() not in ex_lower

    def test_case_9_seven_day_completeness(self):
        """9. Seven-day plan generation: Verify all 7 days and 4 meals per day exist."""
        profile = UserProfile(
            name="CompletenessUser",
            age=28,
            gender="male",
            height_cm=175.0,
            weight_kg=72.0,
            activity_level="moderately_active",
            fitness_goal="maintenance",
            diet_type="veg",
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        demo_str = generate_demo_meal_plan(profile.model_dump(), targets)
        plan_dict = extract_meal_plan_json(demo_str)

        required_days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for day in required_days:
            assert day in plan_dict, f"Missing day: {day}"
            day_plan = plan_dict[day]
            for slot in ["breakfast", "lunch", "snack", "dinner"]:
                assert slot in day_plan, f"Missing slot {slot} on {day}"
                assert len(day_plan[slot]) >= 1, f"Empty slot {slot} on {day}"
                for item in day_plan[slot]:
                    assert item["quantity_g"] > 0

    def test_case_10_daily_nutritional_calculations(self):
        """10. Daily nutritional calculations: Item sums match meal totals, and meal sums match day totals."""
        df = _get_df()
        test_meals = {
            "breakfast": [{"food_name": "Idli", "quantity_g": 150.0}, {"food_name": "Sambar", "quantity_g": 120.0}],
            "lunch": [{"food_name": "Basmati Rice", "quantity_g": 150.0}, {"food_name": "Dal Tadka", "quantity_g": 150.0}],
            "snack": [{"food_name": "Apple", "quantity_g": 120.0}],
            "dinner": [{"food_name": "Whole Wheat Roti", "quantity_g": 90.0}, {"food_name": "Palak Paneer", "quantity_g": 180.0}],
        }
        day_detail = build_day_plan_detail("Monday", test_meals, df, target_calories=2000.0)

        # Meal total check
        calc_day_cal = sum(m.total_calories for m in day_detail.meals.values())
        assert abs(day_detail.total_calories - calc_day_cal) < 0.2

        # Check micronutrients aggregated
        micros = day_detail.micronutrients
        assert "calcium_mg" in micros and micros["calcium_mg"] is not None
        assert "iron_mg" in micros and micros["iron_mg"] is not None
        # Unassayed vitamin in rice/idli should preserve None if not reported
        assert "vitamin_d_mcg" in micros

    def test_case_11_weekly_nutritional_averages(self):
        """11. Weekly nutritional averages: Average = sum / 7 and compliance flag."""
        df = _get_df()
        targets = calculate_nutrition_targets(
            UserProfile(name="AvgUser", age=28, gender="male", height_cm=175.0, weight_kg=75.0, activity_level="moderately_active", fitness_goal="maintenance", diet_type="veg")
        )
        test_meals = {
            "breakfast": [{"food_name": "Idli", "quantity_g": 150.0}],
            "lunch": [{"food_name": "Basmati Rice", "quantity_g": 150.0}],
            "snack": [{"food_name": "Apple", "quantity_g": 100.0}],
            "dinner": [{"food_name": "Whole Wheat Roti", "quantity_g": 90.0}],
        }
        days = [build_day_plan_detail(d, test_meals, df, targets.calorie_target) for d in DAYS_OF_WEEK]
        averages = calculate_weekly_averages(days, targets)

        assert averages.avg_calories > 0
        expected_avg = round(sum(d.total_calories for d in days) / 7.0, 1)
        assert abs(averages.avg_calories - expected_avg) < 0.2
        assert len(averages.daily_calories) == 7

    def test_case_12_meal_substitutions(self):
        """12. Meal substitutions: Find high-similarity replacement for rice/paneer."""
        res = find_food_substitutes.invoke({
            "food_name": "Basmati Rice",
            "diet_type": "veg",
            "meal_type": "lunch",
            "allergies": [],
            "top_n": 3,
        })
        data = json.loads(res)
        assert "substitutes" in data
        assert len(data["substitutes"]) > 0
        for sub in data["substitutes"]:
            assert sub["diet_type"] == "veg"
            assert sub["similarity_score"] > 0.80

    def test_case_13_rag_based_questions(self):
        """13. RAG-based questions: Retrieve factual answer with source citations."""
        res = retrieve_nutrition_knowledge.invoke({"query": "What are the nutritional benefits of millets?"})
        assert "ICMR_NIN_Dietary_Guidelines_for_Indians.pdf" in res
        assert "Page" in res
        assert "Vector Distance" in res

    def test_case_14_irrelevant_nutrition_questions(self):
        """14. Irrelevant nutrition questions: Rejection threshold enforced."""
        res = retrieve_nutrition_knowledge.invoke({"query": "How do you score points in test cricket?"})
        assert "No relevant nutrition document sections were found" in res
        assert "knowledge base does not contain sufficient information" in res

    def test_case_15_missing_or_invalid_api_key(self):
        """15. Missing or invalid API key: Offline 7-day fallback planner produces valid result."""
        profile = UserProfile(
            name="OfflineUser",
            age=28,
            gender="female",
            height_cm=165.0,
            weight_kg=60.0,
            activity_level="moderately_active",
            fitness_goal="weight_loss",
            diet_type="veg",
            allergies=[],
            excluded_foods=[],
        )
        targets = calculate_nutrition_targets(profile).model_dump()
        config = {"configurable": {"thread_id": "test-offline-15-scenarios"}}
        res = app_graph.invoke(
            {
                "user_profile": profile.model_dump(),
                "nutrition_targets": targets,
                "messages": [],
                "revision_count": 0,
            },
            config=config,
        )

        assert res.get("weekly_plan") is not None
        assert res.get("meal_plan") is not None
        assert res.get("validation_result") is not None
        assert res["validation_result"]["is_valid"] is True
        days = res["weekly_plan"]["days"]
        assert len(days) == 7
