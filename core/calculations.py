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

from core.schemas import NutritionTargets
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
