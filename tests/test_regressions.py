"""
tests/test_regressions.py
-------------------------
Regression tests for bugs found during the full-project audit:

1. ``extract_meal_plan_json`` must parse nested fenced JSON (the old
   non-greedy regex stopped at the first inner brace).
2. Validation must report malformed plan shapes instead of raising
   ``AttributeError``.
3. Search, substitution, and validation must agree on allergen synonyms
   (e.g. ``milk`` == ``dairy``) and multi-tag cells.
4. A conversational graph turn must not resurface a previous turn's plan.
"""

import json

from agent.graph import (
    extract_meal_plan_json,
    final_response_node,
    meal_validation_node,
)
from core.validation import run_all_checks, run_weekly_checks
from tools.food_tools import (
    _get_df,
    find_food_substitutes,
    search_food_database,
)


# ── 1. Nested JSON extraction ────────────────────────────────────────────────

def _nested_week_plan() -> dict:
    day = {
        "breakfast": [
            {"food_name": "Idli", "quantity_g": 150},
            {"food_name": "Sambar", "quantity_g": 100},
        ],
        "lunch": [
            {"food_name": "Basmati Rice", "quantity_g": 180},
            {"food_name": "Dal Tadka", "quantity_g": 150},
        ],
        "snack": [{"food_name": "Apple", "quantity_g": 120}],
        "dinner": [
            {"food_name": "Whole Wheat Roti", "quantity_g": 90},
            {"food_name": "Palak Paneer", "quantity_g": 150},
        ],
    }
    return {
        day_name: json.loads(json.dumps(day))
        for day_name in [
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        ]
    }


def test_extract_nested_fenced_json():
    plan = _nested_week_plan()
    text = (
        "Here is your plan with rationale:\n\n"
        "```json\n"
        f"{json.dumps(plan, indent=2)}\n"
        "```\n\n"
        "Enjoy your meals!"
    )
    extracted = extract_meal_plan_json(text)
    assert extracted is not None
    assert len([k for k in extracted if k in plan]) == 7
    assert extracted["monday"]["breakfast"][0]["food_name"] == "Idli"


def test_extract_nested_json_without_fence():
    plan = _nested_week_plan()
    text = f"Plan follows: {json.dumps(plan)} End of plan."
    extracted = extract_meal_plan_json(text)
    assert extracted is not None
    assert extracted["sunday"]["dinner"][1]["quantity_g"] == 150


# ── 2. Malformed plans are reported, not fatal ───────────────────────────────

def test_malformed_plan_reports_issues_without_crashing():
    df = _get_df()
    issues, deviation = run_all_checks(
        plan={"lunch": "oops", "dinner": [{"food_name": "Idli", "quantity_g": 100}]},
        diet_type="veg",
        allergies=[],
        excluded_foods=[],
        calorie_target=2000.0,
        planned_calories=500.0,
        food_df=df,
    )
    assert issues
    assert isinstance(deviation, float)
    assert any("must be a list" in issue for issue in issues)


def test_non_dict_plan_is_reported():
    df = _get_df()
    issues, deviation = run_all_checks(
        plan=["not", "a", "plan"],  # type: ignore[arg-type]
        diet_type="veg",
        allergies=[],
        excluded_foods=[],
        calorie_target=2000.0,
        planned_calories=0.0,
        food_df=df,
    )
    assert issues
    assert deviation == 0.0


def test_weekly_plan_with_bad_quantities_does_not_crash():
    df = _get_df()
    weekly = {
        day: {
            "breakfast": [{"food_name": "Idli", "quantity_g": "abc"}],
            "lunch": [{"food_name": "Dal Tadka", "quantity_g": None}],
            "dinner": "malformed",
        }
        for day in [
            "monday", "tuesday", "wednesday", "thursday",
            "friday", "saturday", "sunday",
        ]
    }
    issues, avg_dev, daily = run_weekly_checks(
        weekly_plan=weekly,
        diet_type="veg",
        allergies=[],
        excluded_foods=[],
        calorie_target=2000.0,
        food_df=df,
    )
    assert issues
    assert isinstance(avg_dev, float)
    assert all(isinstance(value, float) for value in daily.values())


# ── 3. Allergen handling is consistent across tools ─────────────────────────

def test_search_and_validation_agree_on_allergen_synonym():
    # The database tags dairy foods with "dairy"; a user who says "milk"
    # must still have them excluded.
    search = json.loads(search_food_database.invoke({
        "diet_type": "veg",
        "meal_type": "lunch",
        "allergies": ["milk"],
        "excluded_foods": [],
        "top_n": 50,
    }))
    names = {item["food_name"] for item in search.get("items", [])}
    assert "Palak Paneer" not in names
    assert "Dal Makhani" not in names

    df = _get_df()
    issues, _ = run_all_checks(
        plan={"lunch": [{"food_name": "Palak Paneer", "quantity_g": 150}]},
        diet_type="veg",
        allergies=["milk"],
        excluded_foods=[],
        calorie_target=2000.0,
        planned_calories=800.0,
        food_df=df,
    )
    assert any("allergen" in issue.lower() for issue in issues)


def test_multi_tag_allergen_cell_is_detected():
    df = _get_df()
    issues, _ = run_all_checks(
        plan={"lunch": [{"food_name": "Paneer Butter Masala", "quantity_g": 150}]},
        diet_type="veg",
        allergies=["tree_nuts"],
        excluded_foods=[],
        calorie_target=2000.0,
        planned_calories=800.0,
        food_df=df,
    )
    assert any("allergen" in issue.lower() for issue in issues)


def test_profile_canonicalises_allergen_synonyms():
    from core.user_profile import UserProfile

    profile = UserProfile(
        name="Test",
        age=30,
        gender="female",
        height_cm=160.0,
        weight_kg=55.0,
        activity_level="lightly_active",
        fitness_goal="maintenance",
        diet_type="veg",
        allergies=["milk", "egg", "groundnut"],
        excluded_foods=[],
    )
    assert profile.allergies == ["dairy", "eggs", "peanuts"]


def test_substitutes_respect_exclusions_and_allergens():
    res = json.loads(find_food_substitutes.invoke({
        "food_name": "Palak Paneer",
        "diet_type": "veg",
        "meal_type": "dinner",
        "allergies": ["dairy"],
        "excluded_foods": ["Chana Masala"],
        "top_n": 10,
    }))
    subs = res.get("substitutes", [])
    assert subs
    names = {s["food_name"] for s in subs}
    assert "Chana Masala" not in names
    assert all("dairy" not in str(s.get("allergens", "")) for s in subs)


# ── 4. Conversational turns do not emit stale plans ─────────────────────────

def test_conversational_turn_clears_plan_fields():
    state = {
        "messages": [type("Msg", (), {"content": "What are the benefits of millets?"})()],
        "validation_result": {"is_valid": True, "issues": [], "note": "Conversational reply"},
        "meal_plan": {"breakfast": [{"food_name": "Idli", "quantity_g": 100}]},
        "weekly_plan": {"days": [{"day_name": "Monday"}]},
        "nutrition_targets": {"calorie_target": 2000.0},
    }
    result = final_response_node(state)
    assert result["meal_plan"] is None
    assert result["weekly_plan"] is None
    assert "millets" in result["final_response"].lower()


def test_meal_validation_clears_previous_plan_on_chat():
    state = {
        "messages": [type("Msg", (), {"content": "Why this meal?"})()],
        "meal_plan": {"breakfast": [{"food_name": "Idli", "quantity_g": 100}]},
    }
    result = meal_validation_node(state)
    assert result["meal_plan"] is None
    assert result["weekly_plan"] is None
    assert result["validation_result"]["note"] == "Conversational reply"
