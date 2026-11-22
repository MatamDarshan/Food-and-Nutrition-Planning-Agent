"""
core/schemas.py
---------------
Shared Pydantic v2 models used across tools, the agent, and the UI.
Defining them here prevents circular imports and gives every layer
a single source of truth for data shapes.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Nutrition targets ──────────────────────────────────────────────────────────

class NutritionTargets(BaseModel):
    """Daily nutritional requirements derived from a user profile."""

    bmi: float = Field(..., description="Body Mass Index (kg/m²)")
    bmi_category: str = Field(..., description="Underweight / Normal / Overweight / Obese")
    bmr: float = Field(..., description="Basal Metabolic Rate (kcal/day)")
    tdee: float = Field(..., description="Total Daily Energy Expenditure (kcal/day)")
    calorie_target: float = Field(..., description="Adjusted daily calorie goal (kcal/day)")
    protein_g: float = Field(..., description="Daily protein target (g)")
    carbs_g: float = Field(..., description="Daily carbohydrate target (g)")
    fats_g: float = Field(..., description="Daily fat target (g)")
    fiber_g: float = Field(..., description="Daily fibre target (g)")


# ── Food item (matches one CSV row) ───────────────────────────────────────────

class FoodItem(BaseModel):
    """A single food item from the database."""

    food_id: int
    food_name: str
    calories: float
    protein: float
    carbohydrates: float
    fats: float
    fiber: float
    diet_type: str
    meal_type: str
    food_category: str
    ingredients: str
    allergens: str
    glycemic_index: Optional[float] = None


# ── Tool input / output models ─────────────────────────────────────────────────

class FoodSearchQuery(BaseModel):
    """Input for the food database search tool."""

    diet_type: str = Field(..., description="'veg' or 'non-veg'")
    meal_type: str = Field(..., description="'breakfast', 'lunch', 'snack', or 'dinner'")
    max_calories: Optional[float] = Field(
        None, description="Upper calorie limit per 100 g (optional)"
    )
    allergies: list[str] = Field(
        default_factory=list,
        description="List of allergen tags to exclude (e.g. ['gluten', 'dairy'])",
    )
    excluded_foods: list[str] = Field(
        default_factory=list,
        description="Food names the user wants excluded",
    )
    category: Optional[str] = Field(
        None, description="Filter by food category (optional)"
    )
    top_n: int = Field(10, description="Maximum number of results to return")


class MealFoodEntry(BaseModel):
    """One food item with a quantity, used in meal calculations."""

    food_name: str
    quantity_g: float = Field(..., description="Quantity in grams")


class MealSelection(BaseModel):
    """Input for the meal nutrition calculator tool."""

    items: list[MealFoodEntry]


class MealNutrition(BaseModel):
    """Aggregated nutrition for a meal or day."""

    total_calories: float
    total_protein: float
    total_carbs: float
    total_fats: float
    total_fiber: float
    breakdown: list[dict] = Field(
        default_factory=list,
        description="Per-food nutritional breakdown",
    )


class SubstituteQuery(BaseModel):
    """Input for the food substitution finder tool."""

    food_name: str = Field(..., description="Name of the food to replace")
    diet_type: str = Field(..., description="'veg' or 'non-veg'")
    meal_type: str = Field(..., description="Meal context for the substitute")
    allergies: list[str] = Field(default_factory=list)
    top_n: int = Field(3, description="Number of substitutes to return")


class DayMealPlan(BaseModel):
    """Structured one-day meal plan."""

    breakfast: list[MealFoodEntry] = Field(default_factory=list)
    lunch: list[MealFoodEntry] = Field(default_factory=list)
    snack: list[MealFoodEntry] = Field(default_factory=list)
    dinner: list[MealFoodEntry] = Field(default_factory=list)


class MealPlan(BaseModel):
    """Full meal plan submitted for validation."""

    plan: DayMealPlan
    diet_type: str
    allergies: list[str] = Field(default_factory=list)
    excluded_foods: list[str] = Field(default_factory=list)
    calorie_target: float
    protein_g: float
    carbs_g: float
    fats_g: float


class ValidationResult(BaseModel):
    """Output of the meal plan validator tool."""

    is_valid: bool
    issues: list[str] = Field(
        default_factory=list,
        description="List of rule violations (empty when valid)",
    )
    calorie_deviation_pct: float = Field(
        ..., description="% deviation of planned vs target calories"
    )
    planned_calories: float
    planned_protein: float
    planned_carbs: float
    planned_fats: float


# ── 7-Day Structured Meal Plan Models ─────────────────────────────────────────

class FoodItemDetail(BaseModel):
    """Detailed food item with individual nutrition and portion serving."""

    food_name: str
    quantity_g: float = Field(..., description="Quantity in grams")
    serving_display: str = Field(..., description="Household serving (e.g. '2 medium pieces (approx. 150g)')")
    calories: float
    protein: float
    carbohydrates: float
    fat: float
    fiber: float
    diet_type: str = "veg"
    food_category: str = "General"
    micronutrients: dict[str, Optional[float]] = Field(default_factory=dict)


class MealDetail(BaseModel):
    """Individual meal (Breakfast, Lunch, Snack, Dinner) with itemized food & totals."""

    meal_name: str
    label: str = Field(..., description="Display label (e.g. 'Breakfast')")
    items: list[FoodItemDetail] = Field(default_factory=list)
    total_calories: float = 0.0
    total_protein: float = 0.0
    total_carbs: float = 0.0
    total_fat: float = 0.0
    total_fiber: float = 0.0
    micronutrients: dict[str, Optional[float]] = Field(default_factory=dict)


class DayPlanDetail(BaseModel):
    """One day of the 7-day plan containing 4 meals and daily totals."""

    day_name: str = Field(..., description="Monday, Tuesday, etc.")
    meals: dict[str, MealDetail] = Field(default_factory=dict)
    total_calories: float = 0.0
    total_protein: float = 0.0
    total_carbs: float = 0.0
    total_fat: float = 0.0
    total_fiber: float = 0.0
    micronutrients: dict[str, Optional[float]] = Field(default_factory=dict)
    calorie_deviation_pct: float = 0.0


class WeeklyAverages(BaseModel):
    """Calculated weekly averages and target comparison metrics."""

    avg_calories: float
    avg_protein: float
    avg_carbs: float
    avg_fat: float
    avg_fiber: float
    target_calories: float
    target_protein: float
    target_carbs: float
    target_fat: float
    target_fiber: float
    calorie_compliance: bool = True
    macro_compliance: bool = True
    macro_deviations: dict[str, float] = Field(default_factory=dict)
    limitation_note: Optional[str] = None
    daily_calories: dict[str, float] = Field(default_factory=dict)


class WeeklyPlan(BaseModel):
    """Complete 7-day personalized Indian nutrition plan."""

    user_targets: NutritionTargets
    days: list[DayPlanDetail] = Field(default_factory=list)
    weekly_averages: WeeklyAverages
    rationale: str = ""
    validation_result: Optional[ValidationResult] = None
    source_references: list[str] = Field(default_factory=list)

