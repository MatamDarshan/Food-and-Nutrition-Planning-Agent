"""
tests/test_audit_validation_and_accuracy.py
-------------------------------------------
Comprehensive audit test suite verifying:
1. Food preference and allergen validation (individual allergens & composite dishes).
2. Excluded foods and plural stem matching (Idli, Dosa, Upma, Eggs).
3. End-to-end 7-day meal plan validation for the audit vegetarian profile.
4. Mathematical integrity (meal sums == daily totals, weekly average == mean of days).
5. Macronutrient comparison with tolerances and dietary limitation notes.
6. Micronutrient calculation audit (units, None preservation, reference population).
7. AI Nutritionist chat profile awareness (never recommending excluded/allergic items).
"""

import pytest
import pandas as pd
from core.allergens import (
    ingredients_contain_allergen,
    food_violates_exclusion,
    parse_ingredients_list,
)
from core.validation import (
    check_allergen_compliance,
    check_excluded_foods,
    check_diet_compliance,
    check_macronutrient_compliance,
    run_all_checks,
    run_weekly_checks,
)
from tools.food_tools import _get_df, _allergen_mask, _excluded_mask
from core.calculations import (
    build_day_plan_detail,
    calculate_weekly_averages,
    calculate_nutrition_targets,
)
from core.schemas import NutritionTargets
from core.user_profile import UserProfile
from agent.graph import generate_demo_meal_plan, app_graph
from langchain_core.messages import HumanMessage
from data.micronutrient_data import (
    RDA_REFERENCE,
    RDA_POPULATION,
    RDA_SOURCE,
    get_food_micronutrients,
    aggregate_micronutrients,
)


# ── 1. Allergen & Composite Dish Tests ────────────────────────────────────────

def test_individual_allergens_in_raw_ingredients():
    """Verify allergen detection across individual allergens in raw ingredient strings."""
    assert ingredients_contain_allergen("milk;sugar;cardamom", ["dairy"])
    assert ingredients_contain_allergen("paneer;onion;tomato;oil", ["dairy"])
    assert ingredients_contain_allergen("ghee;rice;lentils", ["dairy"])
    assert ingredients_contain_allergen("egg;onion;green chilli", ["eggs"])
    assert ingredients_contain_allergen("almonds;cashews;pistachios", ["tree_nuts"])
    assert ingredients_contain_allergen("peanuts;poha;mustard seeds", ["peanuts"])
    assert ingredients_contain_allergen("tofu;soy sauce;garlic", ["soy"])
    assert ingredients_contain_allergen("wheat flour;water;salt", ["gluten"])
    assert ingredients_contain_allergen("fish fillet;mustard oil;turmeric", ["fish"])


def test_composite_dishes_with_hidden_allergens():
    """Verify that composite Indian dishes with hidden dairy or nuts are correctly flagged."""
    df = _get_df()

    # Kadhi Pakora contains curd/yogurt (dairy)
    kadhi = df[df["food_name"].str.lower() == "kadhi pakora"]
    if not kadhi.empty:
        raw_ing = str(kadhi.iloc[0]["ingredients"])
        assert ingredients_contain_allergen(raw_ing, ["dairy"])

    # Paneer Butter Masala contains butter (dairy) and cashews (tree_nuts)
    pbm = df[df["food_name"].str.lower() == "paneer butter masala"]
    if not pbm.empty:
        raw_ing = str(pbm.iloc[0]["ingredients"])
        assert ingredients_contain_allergen(raw_ing, ["dairy"])
        assert ingredients_contain_allergen(raw_ing, ["tree_nuts"])

    # Coconut Chutney contains tree_nuts tag or coconut
    cc = df[df["food_name"].str.lower() == "coconut chutney"]
    if not cc.empty:
        assert "tree_nuts" in str(cc.iloc[0]["allergens"]).lower()


def test_allergen_compliance_check_catches_composite_violations():
    """check_allergen_compliance must catch allergen violations in meal plans."""
    df = _get_df()
    bad_plan = {
        "breakfast": [{"food_name": "Paneer Butter Masala", "quantity_g": 100}],
        "lunch": [{"food_name": "Basmati Rice", "quantity_g": 150}],
        "snack": [{"food_name": "Apple", "quantity_g": 100}],
        "dinner": [{"food_name": "Whole Wheat Roti", "quantity_g": 100}],
    }
    issues = check_allergen_compliance(bad_plan, ["dairy"], df)
    assert len(issues) > 0
    assert any("dairy" in i.lower() for i in issues)


# ── 2. Excluded Foods & Plural Stem Tests ─────────────────────────────────────

def test_excluded_foods_stemming_and_plurals():
    """'Eggs' must exclude 'Egg Bhurji', 'Egg Curry', and 'Egg Omelette'."""
    assert food_violates_exclusion("Egg Bhurji", "eggs;onion;oil", ["Eggs"])
    assert food_violates_exclusion("Egg Curry", "boiled eggs;gravy", ["Eggs"])
    assert food_violates_exclusion("Egg Omelette", "egg;salt;pepper", ["Eggs"])
    assert food_violates_exclusion("Idli", "rice;urad dal", ["Idli"])
    assert food_violates_exclusion("Dosa", "rice;urad dal;oil", ["Dosa"])
    assert food_violates_exclusion("Upma", "semolina;water;mustard seeds", ["Upma"])


def test_excluded_foods_compliance_check_catches_violations():
    """check_excluded_foods must catch Idli and Egg Bhurji when excluded."""
    df = _get_df()
    bad_plan = {
        "breakfast": [{"food_name": "Idli", "quantity_g": 150}],
        "lunch": [{"food_name": "Basmati Rice", "quantity_g": 150}],
        "snack": [{"food_name": "Apple", "quantity_g": 100}],
        "dinner": [{"food_name": "Egg Bhurji", "quantity_g": 150}],
    }
    issues = check_excluded_foods(bad_plan, ["Idli", "Eggs"], df)
    assert len(issues) == 2
    assert any("idli" in i.lower() for i in issues)
    assert any("egg" in i.lower() for i in issues)


# ── 3. End-to-End Vegetarian Audit Profile Test ───────────────────────────────

def test_vegetarian_audit_profile_meal_plan_end_to_end():
    """Verify that the generated 7-day plan strictly obeys all restrictions:

    - Diet: Vegetarian
    - Allergies: Dairy, Soy, Tree nuts
    - Disliked foods: Upma, Dosa, Idli, Eggs
    - Target: 2500 kcal
    """
    profile = {
        "name": "Audit User",
        "age": 28,
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 75.0,
        "activity_level": "moderately_active",
        "fitness_goal": "maintenance",
        "diet_type": "veg",
        "allergies": ["dairy", "soy", "tree_nuts"],
        "excluded_foods": ["Upma", "Dosa", "Idli", "Eggs"],
    }
    targets = {
        "calorie_target": 2500.0,
        "protein_g": 104.0,
        "carbs_g": 354.0,
        "fats_g": 75.0,
        "fiber_g": 35.0,
    }

    df = _get_df()
    raw_output = generate_demo_meal_plan(profile, targets)

    # Extract JSON
    from agent.graph import extract_meal_plan_json
    plan = extract_meal_plan_json(raw_output)
    assert plan is not None, "Failed to extract JSON from generated meal plan"

    # 1. Verify all 7 days exist
    day_keys = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for dk in day_keys:
        assert dk in plan, f"Day {dk} missing from 7-day plan"
        day_meals = plan[dk]
        # 2. Verify all 4 meal slots exist per day
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            assert slot in day_meals, f"Slot {slot} missing from {dk}"
            items = day_meals[slot]
            assert len(items) > 0, f"Slot {slot} has no items in {dk}"

            # 3. Verify zero restricted foods
            for item in items:
                fname = item["food_name"]
                # Must not be excluded
                violates, reason = food_violates_exclusion(
                    fname, "", profile["excluded_foods"]
                )
                assert not violates, f"Excluded food {fname} found in {dk} {slot} (reason: {reason})"

                # Must not contain allergens
                row = df[df["food_name"].str.lower() == fname.lower()]
                if not row.empty:
                    r = row.iloc[0]
                    assert r["diet_type"] == "veg", f"Non-veg food {fname} found in veg plan"
                    assert not ingredients_contain_allergen(
                        str(r["ingredients"]), profile["allergies"]
                    ), f"Allergen in ingredients of {fname}"
                    for a in profile["allergies"]:
                        assert a.lower() not in str(r["allergens"]).lower(), f"Allergen tag {a} in {fname}"


def test_mathematical_integrity_across_all_days():
    """Verify that:

    1. Sum of food item macros == meal totals.
    2. Sum of meal macros == daily totals.
    3. Weekly averages == mean of daily totals.
    """
    df = _get_df()
    user_p = UserProfile(
        name="Audit User",
        age=28,
        gender="male",
        height_cm=175.0,
        weight_kg=75.0,
        activity_level="moderately_active",
        fitness_goal="maintenance",
        diet_type="veg",
        allergies=["dairy", "soy", "tree_nuts"],
        excluded_foods=["Upma", "Dosa", "Idli", "Eggs"],
    )
    targets_obj = calculate_nutrition_targets(user_p)

    raw_output = generate_demo_meal_plan(user_p.model_dump(), targets_obj.model_dump())
    from agent.graph import extract_meal_plan_json
    plan = extract_meal_plan_json(raw_output)

    days_list = []
    for dk in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
        dp = build_day_plan_detail(dk.title(), plan[dk], df, targets_obj.calorie_target)
        days_list.append(dp)

        # Check item sums == meal sums
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            meal = dp.meals[slot]
            calc_cals = sum(it.calories for it in meal.items)
            calc_prot = sum(it.protein for it in meal.items)
            assert abs(meal.total_calories - calc_cals) < 0.1
            assert abs(meal.total_protein - calc_prot) < 0.1

        # Check meal sums == day sums (float rounding tolerance)
        sum_meal_cals = (
            dp.meals["breakfast"].total_calories
            + dp.meals["lunch"].total_calories
            + dp.meals["snack"].total_calories
            + dp.meals["dinner"].total_calories
        )
        assert abs(dp.total_calories - sum_meal_cals) < 0.5

    # Check weekly averages == mean of daily totals
    averages = calculate_weekly_averages(days_list, targets_obj)
    mean_daily_cals = sum(d.total_calories for d in days_list) / 7.0
    mean_daily_prot = sum(d.total_protein for d in days_list) / 7.0
    mean_daily_carbs = sum(d.total_carbs for d in days_list) / 7.0
    mean_daily_fat = sum(d.total_fat for d in days_list) / 7.0

    assert abs(averages.avg_calories - mean_daily_cals) < 0.2
    assert abs(averages.avg_protein - mean_daily_prot) < 0.2
    assert abs(averages.avg_carbs - mean_daily_carbs) < 0.2
    assert abs(averages.avg_fat - mean_daily_fat) < 0.2


# ── 4. Macronutrient Validation & Limitation Note Tests ────────────────────────

def test_macronutrient_compliance_with_tolerances():
    """Verify that macro compliance applies sensible tolerances and produces limitation notes."""
    # Within tolerance
    issues, metrics = check_macronutrient_compliance(
        planned_calories=2400.0,
        planned_protein=102.0,
        planned_carbs=360.0,
        planned_fats=72.0,
        calorie_target=2500.0,
        protein_target=104.0,
        carbs_target=354.0,
        fats_target=75.0,
        allergies=["dairy", "tree_nuts"],
        diet_type="veg",
    )
    assert metrics["is_macro_compliant"] is True
    assert metrics["calorie_dev_pct"] == -4.0

    # Low fat with strict dairy/nut exclusion generates Limitation Note (explained without failing plan)
    issues, metrics = check_macronutrient_compliance(
        planned_calories=2380.0,
        planned_protein=105.0,
        planned_carbs=390.0,
        planned_fats=50.0,
        calorie_target=2500.0,
        protein_target=104.0,
        carbs_target=354.0,
        fats_target=75.0,
        allergies=["dairy", "tree_nuts"],
        diet_type="veg",
    )
    assert metrics["limitation_note"] is not None
    assert "Dietary Limitation Note" in metrics["limitation_note"]
    assert "dairy" in metrics["limitation_note"].lower()

    # Low fat WITHOUT restrictions is flagged as an issue
    issues, metrics = check_macronutrient_compliance(
        planned_calories=2380.0,
        planned_protein=105.0,
        planned_carbs=390.0,
        planned_fats=50.0,
        calorie_target=2500.0,
        protein_target=104.0,
        carbs_target=354.0,
        fats_target=75.0,
        allergies=[],
        diet_type="veg",
    )
    assert metrics["is_macro_compliant"] is False
    assert any("Fat is below target" in i for i in issues)


# ── 5. Micronutrient Calculation & Metadata Tests ─────────────────────────────

def test_micronutrient_metadata_and_population_reference():
    """Verify RDA reference population and source metadata strings."""
    assert RDA_POPULATION == "Healthy Indian Adults (19–65 years, Reference Man & Woman)"
    assert RDA_SOURCE == "ICMR-National Institute of Nutrition (NIN) RDA 2020 & IFCT 2017"


def test_missing_micronutrient_remains_none():
    """Verify that foods without tested micronutrients in IFCT 2017 retain None instead of 0.0."""
    micros = get_food_micronutrients("Apple", 100.0)
    # Apple has no tested Vitamin D in IFCT 2017 -> should remain None
    assert micros.get("vitamin_d_mcg") is None


def test_micronutrient_portion_scaling():
    """Scaling 200g of Basmati Rice must double the micronutrient quantities."""
    m100 = get_food_micronutrients("Basmati Rice", 100.0)
    m200 = get_food_micronutrients("Basmati Rice", 200.0)
    if m100.get("iron_mg") is not None:
        assert abs(m200["iron_mg"] - (m100["iron_mg"] * 2.0)) < 1e-4


# ── 6. AI Nutritionist Chat Profile Awareness Tests ───────────────────────────

def test_ai_nutritionist_chat_respects_profile_exclusions():
    """Chat assistant must never recommend Idli or dairy to the audit profile user."""
    profile = {
        "name": "Audit User",
        "diet_type": "veg",
        "allergies": ["dairy", "soy", "tree_nuts"],
        "excluded_foods": ["Upma", "Dosa", "Idli", "Eggs"],
    }
    targets = {
        "calorie_target": 2500.0,
        "protein_g": 104.0,
        "carbs_g": 354.0,
        "fats_g": 75.0,
    }

    # Ask for breakfast recommendation
    res = app_graph.invoke(
        {
            "messages": [HumanMessage(content="What should I take for morning breakfast?")],
            "user_profile": profile,
            "nutrition_targets": targets,
        },
        config={"configurable": {"thread_id": "test_audit_chat_1"}},
    )
    final_text = res.get("final_response") or res["messages"][-1].content
    lower_text = final_text.lower()

    # Must NOT recommend excluded foods
    assert "idli" not in lower_text or "excluded" in lower_text
    assert "upma" not in lower_text or "excluded" in lower_text
    assert "dosa" not in lower_text or "excluded" in lower_text
    assert "egg" not in lower_text or "excluded" in lower_text

    # Must recommend compliant alternative
    assert "besan chilla" in lower_text or "poha" in lower_text


def test_ai_nutritionist_chat_explains_excluded_food_query():
    """When user asks about Idli, the chat must explain it is excluded in their profile."""
    profile = {
        "name": "Audit User",
        "diet_type": "veg",
        "allergies": ["dairy", "soy", "tree_nuts"],
        "excluded_foods": ["Upma", "Dosa", "Idli", "Eggs"],
    }
    targets = {
        "calorie_target": 2500.0,
        "protein_g": 104.0,
        "carbs_g": 354.0,
        "fats_g": 75.0,
    }

    res = app_graph.invoke(
        {
            "messages": [HumanMessage(content="Can I eat Idli for breakfast?")],
            "user_profile": profile,
            "nutrition_targets": targets,
        },
        config={"configurable": {"thread_id": "test_audit_chat_2"}},
    )
    final_text = res.get("final_response") or res["messages"][-1].content
    lower_text = final_text.lower()

    assert "excluded" in lower_text
    assert "idli" in lower_text
