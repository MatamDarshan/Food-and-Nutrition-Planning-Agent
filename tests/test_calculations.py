"""
tests/test_calculations.py
---------------------------
Unit tests for core nutritional calculations:
- BMI & Category
- BMR (Mifflin-St Jeor for male and female)
- TDEE across all PAL factors
- Goal-based Calorie adjustments & 1200 kcal floor
- Macronutrient targets (Protein, Fat, Carbs, Fiber)
- UserProfile Pydantic validation & error catching
"""

import pytest
from pydantic import ValidationError
from core.user_profile import UserProfile
from core.calculations import (
    calculate_bmi,
    get_bmi_category,
    calculate_bmr,
    calculate_tdee,
    calculate_calorie_target,
    calculate_protein_target,
    calculate_fat_target,
    calculate_carb_target,
    calculate_fiber_target,
    calculate_nutrition_targets,
)


class TestBMICalculations:
    def test_normal_bmi(self):
        bmi = calculate_bmi(weight_kg=70.0, height_cm=175.0)
        assert bmi == 22.86
        assert get_bmi_category(bmi) == "Normal weight"

    def test_overweight_bmi(self):
        bmi = calculate_bmi(weight_kg=85.0, height_cm=175.0)
        assert bmi == 27.76
        assert get_bmi_category(bmi) == "Overweight"

    def test_underweight_bmi(self):
        bmi = calculate_bmi(weight_kg=45.0, height_cm=165.0)
        assert bmi == 16.53
        assert get_bmi_category(bmi) == "Underweight"

    def test_obese_bmi(self):
        bmi = calculate_bmi(weight_kg=105.0, height_cm=170.0)
        assert bmi == 36.33
        assert get_bmi_category(bmi) == "Obese"


class TestBMRCalculations:
    def test_bmr_male(self):
        # Mifflin-St Jeor: (10*80) + (6.25*180) - (5*25) + 5 = 800 + 1125 - 125 + 5 = 1805.0
        bmr = calculate_bmr(weight_kg=80.0, height_cm=180.0, age=25, gender="male")
        assert bmr == 1805.0

    def test_bmr_female(self):
        # Mifflin-St Jeor: (10*60) + (6.25*165) - (5*30) - 161 = 600 + 1031.25 - 150 - 161 = 1320.25
        bmr = calculate_bmr(weight_kg=60.0, height_cm=165.0, age=30, gender="female")
        assert bmr == 1320.25


class TestTDEECalculations:
    @pytest.mark.parametrize(
        "activity,multiplier",
        [
            ("sedentary", 1.2),
            ("lightly_active", 1.375),
            ("moderately_active", 1.55),
            ("very_active", 1.725),
            ("extra_active", 1.9),
        ],
    )
    def test_tdee_multipliers(self, activity, multiplier):
        bmr = 1500.0
        expected = round(bmr * multiplier, 2)
        assert calculate_tdee(bmr, activity) == expected


class TestCalorieAndMacroTargets:
    def test_weight_loss_deficit(self):
        tdee = 2500.0
        assert calculate_calorie_target(tdee, "weight_loss") == 2000.0

    def test_muscle_gain_surplus(self):
        tdee = 2500.0
        assert calculate_calorie_target(tdee, "muscle_gain") == 2800.0

    def test_maintenance_no_change(self):
        tdee = 2500.0
        assert calculate_calorie_target(tdee, "maintenance") == 2500.0

    def test_calorie_floor_protection(self):
        # Very low TDEE with deficit must not drop below 1200 kcal
        assert calculate_calorie_target(tdee=1400.0, fitness_goal="weight_loss") == 1200.0
        assert calculate_calorie_target(tdee=1000.0, fitness_goal="weight_loss") == 1200.0

    def test_protein_calculation(self):
        # Weight loss uses 1.8 g/kg
        assert calculate_protein_target(weight_kg=80.0, fitness_goal="weight_loss") == 144.0
        # Muscle gain uses 2.2 g/kg
        assert calculate_protein_target(weight_kg=60.0, fitness_goal="muscle_gain") == 132.0
        # Maintenance uses 1.6 g/kg
        assert calculate_protein_target(weight_kg=70.0, fitness_goal="maintenance") == 112.0

    def test_macro_summation_consistency(self):
        cal_target = 2000.0
        prot = calculate_protein_target(75.0, "maintenance") # 120.0g = 480 kcal
        fat = calculate_fat_target(cal_target)               # 60.0g = 540 kcal
        carbs = calculate_carb_target(cal_target, prot, fat) # (2000 - 480 - 540)/4 = 245.0g = 980 kcal
        fiber = calculate_fiber_target(cal_target)           # 2.0 * 14 = 28.0g

        total_computed_cal = (prot * 4.0) + (fat * 9.0) + (carbs * 4.0)
        assert abs(total_computed_cal - cal_target) < 5.0
        assert fiber == 28.0


class TestUserProfileValidation:
    def test_valid_profile_creation(self, sample_veg_profile: UserProfile):
        assert sample_veg_profile.name == "Arjun"
        assert sample_veg_profile.height_m == 1.75
        assert sample_veg_profile.allergies == ["dairy"]

    def test_invalid_age_raises(self):
        with pytest.raises(ValidationError):
            UserProfile(
                name="Child",
                age=5, # Under 10
                gender="male",
                height_cm=120.0,
                weight_kg=25.0,
                activity_level="sedentary",
                fitness_goal="maintenance",
                diet_type="veg",
            )

    def test_invalid_allergen_raises(self):
        with pytest.raises(ValidationError):
            UserProfile(
                name="User",
                age=25,
                gender="female",
                height_cm=160.0,
                weight_kg=55.0,
                activity_level="sedentary",
                fitness_goal="maintenance",
                diet_type="veg",
                allergies=["non_existent_allergen"],
            )
