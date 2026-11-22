"""Pydantic request/response contracts for the REST API."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

ExtendedDiet = Literal["veg", "vegan", "eggetarian", "non-veg"]
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(value: str) -> str:
    cleaned = str(value).strip().lower()
    if not _EMAIL_RE.match(cleaned):
        raise ValueError("Enter a valid email address.")
    return cleaned


class SignUpRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: str
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _valid_email(value)


class SignInRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return _valid_email(value)


class UserOut(BaseModel):
    id: str
    name: str
    email: str


class AuthResponse(BaseModel):
    token: str
    user: UserOut


class ProfileIn(BaseModel):
    """Onboarding payload. Extra preferences are additive to UserProfile."""

    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=18, le=100)
    gender: Literal["male", "female"]
    height_cm: float = Field(gt=50, le=300)
    weight_kg: float = Field(gt=10, le=500)
    activity_level: Literal[
        "sedentary", "lightly_active", "moderately_active",
        "very_active", "extra_active",
    ]
    fitness_goal: Literal["weight_loss", "maintenance", "muscle_gain"]
    diet_type: ExtendedDiet = "veg"
    allergies: list[str] = Field(default_factory=list)
    disliked_foods: list[str] = Field(default_factory=list)
    cuisine_preferences: list[str] = Field(default_factory=list)
    budget: Literal["low", "medium", "premium"] = "medium"
    cooking_time_minutes: int = Field(default=30, ge=5, le=180)
    health_conditions: list[str] = Field(default_factory=list)


class ProfileOut(ProfileIn):
    pass


class PlanGenerateRequest(BaseModel):
    profile: ProfileIn
    mode: Literal["fast", "ai"] = "fast"


class PlanUpdateRequest(BaseModel):
    plan_id: str
    day: str
    meal: str


class RegenerateMealRequest(PlanUpdateRequest):
    pass


class SwapMealRequest(PlanUpdateRequest):
    food_name: str


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatMessageIn] = Field(default_factory=list)
    plan_id: Optional[str] = None


class CitationOut(BaseModel):
    source: str
    page: Optional[int] = None
    condition: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    citations: list[CitationOut] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ShoppingItem(BaseModel):
    name: str
    total_grams: float
    serving: str
    category: str
    days: list[str] = Field(default_factory=list)


class GroceryResponse(BaseModel):
    items: list[ShoppingItem]
    checked: dict[str, bool] = Field(default_factory=dict)


class FoodOut(BaseModel):
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
    image: Optional[str] = None
    prep_time_minutes: Optional[int] = None


class FoodSearchResponse(BaseModel):
    items: list[FoodOut]
    count: int


class SubstituteOut(BaseModel):
    food_name: str
    calories: float
    protein: float
    similarity_score: float
    image: Optional[str] = None
    reason: Optional[str] = None
