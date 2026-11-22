"""
core/user_profile.py
--------------------
Pydantic v2 UserProfile model.

Collects and validates all user inputs needed to compute nutritional
requirements and generate a personalised meal plan.
"""

from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from core.allergens import canonicalize_allergen


# ── Enumerations (string literals for clean error messages) ───────────────────

ActivityLevel = Literal[
    "sedentary",           # desk job, little / no exercise
    "lightly_active",      # light exercise 1–3 days/week
    "moderately_active",   # moderate exercise 3–5 days/week
    "very_active",         # hard exercise 6–7 days/week
    "extra_active",        # very hard exercise / physical job
]

FitnessGoal = Literal[
    "weight_loss",
    "maintenance",
    "muscle_gain",
]

DietType = Literal["veg", "non-veg"]

Gender = Literal["male", "female"]


# ── Main model ────────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    """
    Validated user profile.

    All fields are validated on construction.  Pass keyword arguments or
    build from a dict:  UserProfile(**form_data)
    """

    # ── Demographics ──────────────────────────────────────────────────────────
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="User's full name",
    )
    age: int = Field(
        ...,
        ge=18,
        le=100,
        description="Age in years (18–100 for healthy adults)",
    )
    gender: Gender = Field(
        ...,
        description="'male' or 'female' — used in BMR formula",
    )
    height_cm: float = Field(
        ...,
        gt=50,
        le=300,
        description="Height in centimetres",
    )
    weight_kg: float = Field(
        ...,
        gt=10,
        le=500,
        description="Weight in kilograms",
    )

    # ── Lifestyle ─────────────────────────────────────────────────────────────
    activity_level: ActivityLevel = Field(
        ...,
        description=(
            "sedentary | lightly_active | moderately_active | "
            "very_active | extra_active"
        ),
    )
    fitness_goal: FitnessGoal = Field(
        ...,
        description="weight_loss | maintenance | muscle_gain",
    )

    # ── Dietary preferences ───────────────────────────────────────────────────
    diet_type: DietType = Field(
        ...,
        description="'veg' or 'non-veg'",
    )
    allergies: list[str] = Field(
        default_factory=list,
        description=(
            "Known allergen tags from: gluten, dairy, eggs, fish, "
            "tree_nuts, peanuts, soy, shellfish"
        ),
    )
    excluded_foods: list[str] = Field(
        default_factory=list,
        description="Food names the user does not want in their plan",
    )

    # ── Optional health context ───────────────────────────────────────────────
    health_conditions: Optional[list[str]] = Field(
        default=None,
        description="e.g. ['diabetes', 'hypertension'] — informational only",
    )

    # ── Validators ────────────────────────────────────────────────────────────

    @field_validator("allergies", mode="before")
    @classmethod
    def normalise_allergies(cls, v: list) -> list[str]:
        """Canonicalise allergen tags; synonyms such as ``milk`` become ``dairy``."""
        known = {
            "gluten", "dairy", "eggs", "fish",
            "tree_nuts", "peanuts", "soy", "shellfish",
        }
        cleaned: list[str] = []
        for tag in v:
            canonical = canonicalize_allergen(tag)
            if canonical is None:
                continue
            if canonical not in known:
                raise ValueError(
                    f"Unknown allergen '{tag}'. "
                    f"Valid tags: {sorted(known)}"
                )
            if canonical not in cleaned:
                cleaned.append(canonical)
        return cleaned

    @field_validator("excluded_foods", mode="before")
    @classmethod
    def normalise_excluded(cls, v: list) -> list[str]:
        """Strip whitespace from food names."""
        return [str(item).strip() for item in v if str(item).strip()]

    @model_validator(mode="after")
    def weight_loss_minimum_age(self) -> "UserProfile":
        """Warn-safe: muscle-gain goal for very young users is unusual but allowed."""
        return self

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def height_m(self) -> float:
        return self.height_cm / 100.0

    def summary(self) -> str:
        """Human-readable one-liner for logging / prompts."""
        return (
            f"{self.name}, {self.age}y {self.gender}, "
            f"{self.weight_kg}kg / {self.height_cm}cm, "
            f"{self.activity_level}, goal={self.fitness_goal}, "
            f"diet={self.diet_type}"
            + (f", allergies={self.allergies}" if self.allergies else "")
            + (f", excludes={self.excluded_foods}" if self.excluded_foods else "")
        )
