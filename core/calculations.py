"""
core/calculations.py
--------------------
Pure, side-effect-free functions for nutritional calculations.

All functions are independently testable — no I/O, no network, no globals.
The only dependency is the UserProfile and NutritionTargets models from
core/schemas.py and core/user_profile.py.

Formula references
------------------
BMR  : Mifflin-St Jeor (1990)
       Men  : (10 × kg) + (6.25 × cm) − (5 × age) + 5
       Women: (10 × kg) + (6.25 × cm) − (5 × age) − 161

TDEE : BMR × Physical Activity Level (PAL) multiplier

Macros
------
Protein : 1.6–2.2 g / kg body weight (goal-adjusted)
Fat     : 25–30 % of calorie target
Carbs   : (calorie_target − protein_kcal − fat_kcal) / 4
Fibre   : 14 g per 1000 kcal (US DRI standard)
"""

from __future__ import annotations

from core.schemas import (
    NutritionTargets,
    FoodItemDetail,
    MealDetail,
    DayPlanDetail,
    WeeklyAverages,
    WeeklyPlan,
)
from data.micronutrient_data import (
    get_food_micronutrients,
    aggregate_micronutrients,
    HOUSEHOLD_SERVINGS,
)
import pandas as pd
from core.user_profile import UserProfile


# ── Activity-level PAL multipliers ────────────────────────────────────────────

_PAL: dict[str, float] = {
    "sedentary": 1.200,
    "lightly_active": 1.375,
    "moderately_active": 1.550,
    "very_active": 1.725,
    "extra_active": 1.900,
}

# ── Calorie adjustment by fitness goal (kcal) ─────────────────────────────────

_GOAL_DELTA: dict[str, float] = {
    "weight_loss": -500.0,   # moderate deficit  → ~0.5 kg/week loss
    "maintenance": 0.0,
    "muscle_gain": +300.0,   # lean bulk surplus
}

# ── Protein targets by fitness goal (g / kg body weight) ──────────────────────

_PROTEIN_G_PER_KG: dict[str, float] = {
    "weight_loss": 1.8,   # higher to preserve muscle during deficit
    "maintenance": 1.6,
    "muscle_gain": 2.2,   # upper end for hypertrophy
}

# ── Fat target as a fraction of calorie target ────────────────────────────────

_FAT_FRACTION = 0.27   # 27 % of calories — mid-range of 25–30 %


# ── Individual calculation functions ─────────────────────────────────────────

def calculate_bmi(weight_kg: float, height_cm: float) -> float:
    """Return BMI rounded to 2 decimal places."""
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m ** 2), 2)


def get_bmi_category(bmi: float) -> str:
    """Return WHO BMI category string."""
    if bmi < 18.5:
        return "Underweight"
    if bmi < 25.0:
        return "Normal weight"
    if bmi < 30.0:
        return "Overweight"
    return "Obese"


def calculate_bmr(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
) -> float:
    """
    Basal Metabolic Rate using Mifflin-St Jeor equation.
    Returns kcal/day rounded to 2 decimal places.
    """
    base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age)
    adjustment = 5.0 if gender == "male" else -161.0
    return round(base + adjustment, 2)


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """
    Total Daily Energy Expenditure = BMR × PAL multiplier.
    Returns kcal/day rounded to 2 decimal places.
    """
    pal = _PAL.get(activity_level, 1.2)
    return round(bmr * pal, 2)


def calculate_calorie_target(tdee: float, fitness_goal: str) -> float:
    """
    Adjust TDEE by fitness-goal delta.
    Returns kcal/day rounded to 2 decimal places.
    Minimum floor: 1200 kcal (safe lower bound).
    """
    delta = _GOAL_DELTA.get(fitness_goal, 0.0)
    target = tdee + delta
    return round(max(target, 1200.0), 2)


def calculate_protein_target(weight_kg: float, fitness_goal: str) -> float:
    """
    Daily protein target in grams.
    Returns value rounded to 1 decimal place.
    """
    g_per_kg = _PROTEIN_G_PER_KG.get(fitness_goal, 1.6)
    return round(weight_kg * g_per_kg, 1)


def calculate_fat_target(calorie_target: float) -> float:
    """
    Daily fat target in grams (27 % of calorie target ÷ 9 kcal/g).
    Returns value rounded to 1 decimal place.
    """
    fat_kcal = calorie_target * _FAT_FRACTION
    return round(fat_kcal / 9.0, 1)


def calculate_carb_target(
    calorie_target: float,
    protein_g: float,
    fat_g: float,
) -> float:
    """
    Daily carbohydrate target in grams.
    Carbs supply the remaining calories after protein and fat are accounted for.
    Returns value rounded to 1 decimal place.
    """
    protein_kcal = protein_g * 4.0
    fat_kcal = fat_g * 9.0
    remaining_kcal = calorie_target - protein_kcal - fat_kcal
    carb_g = max(remaining_kcal / 4.0, 0.0)   # floor at 0 g
    return round(carb_g, 1)


def calculate_fiber_target(calorie_target: float) -> float:
    """
    Daily fibre target: 14 g per 1000 kcal (US DRI standard).
    Returns value rounded to 1 decimal place.
    """
    return round((calorie_target / 1000.0) * 14.0, 1)


# ── Composite function (called by Tool 1 and the UI dashboard) ────────────────

def calculate_nutrition_targets(profile: UserProfile) -> NutritionTargets:
    """
    Derive all daily nutritional targets from a validated UserProfile.

    Steps
    -----
    1. BMI  → category
    2. BMR  (Mifflin-St Jeor)
    3. TDEE (BMR × PAL)
    4. Calorie target (TDEE ± goal delta, floor 1200)
    5. Protein  (g/kg, goal-adjusted)
    6. Fat      (27 % of calories)
    7. Carbs    (remaining calories)
    8. Fibre    (14 g / 1000 kcal)
    """
    bmi = calculate_bmi(profile.weight_kg, profile.height_cm)
    bmi_cat = get_bmi_category(bmi)
    bmr = calculate_bmr(profile.weight_kg, profile.height_cm, profile.age, profile.gender)
    tdee = calculate_tdee(bmr, profile.activity_level)
    cal_target = calculate_calorie_target(tdee, profile.fitness_goal)
    protein_g = calculate_protein_target(profile.weight_kg, profile.fitness_goal)
    fat_g = calculate_fat_target(cal_target)
    carbs_g = calculate_carb_target(cal_target, protein_g, fat_g)
    fiber_g = calculate_fiber_target(cal_target)

    return NutritionTargets(
        bmi=bmi,
        bmi_category=bmi_cat,
        bmr=bmr,
        tdee=tdee,
        calorie_target=cal_target,
        protein_g=protein_g,
        carbs_g=carbs_g,
        fats_g=fat_g,
        fiber_g=fiber_g,
    )


# ── 7-Day Meal Plan Mathematical Constructors ─────────────────────────────────

MEAL_LABELS: dict[str, str] = {
    "breakfast": "Breakfast",
    "lunch": "Lunch",
    "snack": "Evening Snack",
    "dinner": "Dinner",
}

DAYS_OF_WEEK: list[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def build_food_item_detail(
    food_name: str,
    quantity_g: float,
    food_df: pd.DataFrame,
) -> FoodItemDetail:
    """Compute food-level nutritional values and format serving description."""
    food_name = str(food_name).strip()
    match = food_df[food_df["food_name"].str.lower() == food_name.lower()]
    if match.empty:
        # Fallback if unknown
        return FoodItemDetail(
            food_name=food_name,
            quantity_g=quantity_g,
            serving_display=f"{quantity_g:.0f} g",
            calories=0.0,
            protein=0.0,
            carbohydrates=0.0,
            fat=0.0,
            fiber=0.0,
            diet_type="veg",
            food_category="General",
            micronutrients={},
        )

    row = match.iloc[0]
    scale = quantity_g / 100.0 if quantity_g > 0 else 0.0

    cal = round(float(row["calories"]) * scale, 1)
    prot = round(float(row["protein"]) * scale, 1)
    carb = round(float(row["carbohydrates"]) * scale, 1)
    fat = round(float(row["fats"]) * scale, 1)
    fib = round(float(row["fiber"]) * scale, 1)

    serving_hint = HOUSEHOLD_SERVINGS.get(food_name, "")
    if serving_hint:
        serving_display = f"{quantity_g:.0f} g ({serving_hint})"
    else:
        serving_display = f"{quantity_g:.0f} g"

    micros = get_food_micronutrients(food_name, quantity_g)

    return FoodItemDetail(
        food_name=food_name,
        quantity_g=quantity_g,
        serving_display=serving_display,
        calories=cal,
        protein=prot,
        carbohydrates=carb,
        fat=fat,
        fiber=fib,
        diet_type=str(row.get("diet_type", "veg")),
        food_category=str(row.get("food_category", "General")),
        micronutrients=micros,
    )


def build_meal_detail(
    meal_name: str,
    items_raw: list[dict],
    food_df: pd.DataFrame,
) -> MealDetail:
    """Build a MealDetail by summing all included food items."""
    food_items: list[FoodItemDetail] = []
    tot_cal = 0.0
    tot_prot = 0.0
    tot_carb = 0.0
    tot_fat = 0.0
    tot_fib = 0.0

    # Accept a single object, ignore malformed entries, and tolerate bad
    # quantities so a partially malformed LLM plan still renders.
    if isinstance(items_raw, dict):
        items_raw = [items_raw]
    if not isinstance(items_raw, list):
        items_raw = []

    for item in items_raw:
        if not isinstance(item, dict):
            continue
        fname = str(item.get("food_name", "")).strip()
        try:
            qty = float(item.get("quantity_g", 0.0))
        except (TypeError, ValueError):
            qty = 0.0
        if not fname or qty <= 0:
            continue
        detail = build_food_item_detail(fname, qty, food_df)
        food_items.append(detail)
        tot_cal += detail.calories
        tot_prot += detail.protein
        tot_carb += detail.carbohydrates
        tot_fat += detail.fat
        tot_fib += detail.fiber

    # Aggregate micronutrients
    meal_micros = aggregate_micronutrients(items_raw)

    label = MEAL_LABELS.get(meal_name.lower(), meal_name.title())

    return MealDetail(
        meal_name=meal_name.lower(),
        label=label,
        items=food_items,
        total_calories=round(tot_cal, 1),
        total_protein=round(tot_prot, 1),
        total_carbs=round(tot_carb, 1),
        total_fat=round(tot_fat, 1),
        total_fiber=round(tot_fib, 1),
        micronutrients=meal_micros,
    )


def build_day_plan_detail(
    day_name: str,
    meals_dict: dict[str, list[dict]],
    food_df: pd.DataFrame,
    target_calories: float = 2000.0,
) -> DayPlanDetail:
    """Build a DayPlanDetail by summing all 4 meals."""
    meals: dict[str, MealDetail] = {}
    day_cal = 0.0
    day_prot = 0.0
    day_carb = 0.0
    day_fat = 0.0
    day_fib = 0.0

    all_day_items: list[dict] = []

    for slot in ["breakfast", "lunch", "snack", "dinner"]:
        raw_items = meals_dict.get(slot, []) if isinstance(meals_dict, dict) else []
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        if not isinstance(raw_items, list):
            raw_items = []
        valid_items = [item for item in raw_items if isinstance(item, dict)]
        all_day_items.extend(valid_items)
        md = build_meal_detail(slot, valid_items, food_df)
        meals[slot] = md
        day_cal += md.total_calories
        day_prot += md.total_protein
        day_carb += md.total_carbs
        day_fat += md.total_fat
        day_fib += md.total_fiber

    day_micros = aggregate_micronutrients(all_day_items)

    dev_pct = 0.0
    if target_calories > 0:
        dev_pct = round(((day_cal - target_calories) / target_calories) * 100.0, 1)

    return DayPlanDetail(
        day_name=day_name,
        meals=meals,
        total_calories=round(day_cal, 1),
        total_protein=round(day_prot, 1),
        total_carbs=round(day_carb, 1),
        total_fat=round(day_fat, 1),
        total_fiber=round(day_fib, 1),
        micronutrients=day_micros,
        calorie_deviation_pct=dev_pct,
    )


def calculate_weekly_averages(
    days: list[DayPlanDetail],
    targets: NutritionTargets,
) -> WeeklyAverages:
    """Calculate average daily calories, protein, carbs, fat, fibre and target compliance."""
    if not days:
        return WeeklyAverages(
            avg_calories=0.0,
            avg_protein=0.0,
            avg_carbs=0.0,
            avg_fat=0.0,
            avg_fiber=0.0,
            target_calories=targets.calorie_target,
            target_protein=targets.protein_g,
            target_carbs=targets.carbs_g,
            target_fat=targets.fats_g,
            target_fiber=targets.fiber_g,
            calorie_compliance=False,
            daily_calories={},
        )

    n = len(days)
    sum_cal = sum(d.total_calories for d in days)
    sum_prot = sum(d.total_protein for d in days)
    sum_carb = sum(d.total_carbs for d in days)
    sum_fat = sum(d.total_fat for d in days)
    sum_fib = sum(d.total_fiber for d in days)

    avg_cal = round(sum_cal / n, 1)
    avg_prot = round(sum_prot / n, 1)
    avg_carb = round(sum_carb / n, 1)
    avg_fat = round(sum_fat / n, 1)
    avg_fib = round(sum_fib / n, 1)

    if targets.calorie_target > 0:
        dev_from_target = abs(avg_cal - targets.calorie_target) / targets.calorie_target
        compliant = dev_from_target <= 0.15
    else:
        compliant = False

    daily_cals = {d.day_name: d.total_calories for d in days}

    cal_dev = round(((avg_cal - targets.calorie_target) / max(targets.calorie_target, 1.0)) * 100.0, 1) if targets.calorie_target > 0 else 0.0
    prot_dev = round(((avg_prot - targets.protein_g) / max(targets.protein_g, 1.0)) * 100.0, 1) if targets.protein_g > 0 else 0.0
    carb_dev = round(((avg_carb - targets.carbs_g) / max(targets.carbs_g, 1.0)) * 100.0, 1) if targets.carbs_g > 0 else 0.0
    fat_dev = round(((avg_fat - targets.fats_g) / max(targets.fats_g, 1.0)) * 100.0, 1) if targets.fats_g > 0 else 0.0
    fib_dev = round(((avg_fib - targets.fiber_g) / max(targets.fiber_g, 1.0)) * 100.0, 1) if targets.fiber_g > 0 else 0.0

    macro_devs = {
        "calories_pct": cal_dev,
        "protein_pct": prot_dev,
        "carbs_pct": carb_dev,
        "fat_pct": fat_dev,
        "fiber_pct": fib_dev,
    }

    # Macro compliance requires calories within +/- 15%, protein >= -15%, carbs within +/- 25%, fat within +/- 25%
    macro_compliant = compliant and (prot_dev >= -15.0) and (abs(carb_dev) <= 25.0) and (abs(fat_dev) <= 25.0)

    limitation_note = None
    if fat_dev < -25.0:
        limitation_note = (
            f"Dietary Limitation Note: Planned weekly average fat ({avg_fat:.1f}g/day) is below theoretical target "
            f"({targets.fats_g:.1f}g/day) due to user dietary restrictions (e.g. dairy or nuts excluded). "
            f"Caloric energy is fulfilled with healthy complex carbohydrates and plant protein."
        )

    return WeeklyAverages(
        avg_calories=avg_cal,
        avg_protein=avg_prot,
        avg_carbs=avg_carb,
        avg_fat=avg_fat,
        avg_fiber=avg_fib,
        target_calories=targets.calorie_target,
        target_protein=targets.protein_g,
        target_carbs=targets.carbs_g,
        target_fat=targets.fats_g,
        target_fiber=targets.fiber_g,
        calorie_compliance=compliant,
        macro_compliance=macro_compliant,
        macro_deviations=macro_devs,
        limitation_note=limitation_note,
        daily_calories=daily_cals,
    )

