"""
tests/conftest.py
-----------------
Pytest shared fixtures for UserProfile, NutritionTargets, and Food DataFrame.
"""
import os

# The suite is intentionally hermetic: it must produce identical results on a
# developer machine with a real API key in .env and on a clean CI machine.
# Force the documented deterministic/offline engine before any project module
# (and therefore config.settings) is imported.
os.environ["GOOGLE_API_KEY"] = ""
os.environ.pop("GEMINI_API_KEY", None)

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
try:
    import tqdm
    tqdm.tqdm.monitor_interval = 0
except Exception:
    pass

import pytest
import pandas as pd
from core.user_profile import UserProfile
from core.calculations import calculate_nutrition_targets
from tools.food_tools import _get_df


@pytest.fixture
def sample_veg_profile() -> UserProfile:
    return UserProfile(
        name="Arjun",
        age=28,
        gender="male",
        height_cm=175.0,
        weight_kg=82.0,
        activity_level="moderately_active",
        fitness_goal="weight_loss",
        diet_type="veg",
        allergies=["dairy"],
        excluded_foods=["Samosa"],
    )


@pytest.fixture
def sample_non_veg_profile() -> UserProfile:
    return UserProfile(
        name="Priya",
        age=25,
        gender="female",
        height_cm=165.0,
        weight_kg=58.0,
        activity_level="very_active",
        fitness_goal="muscle_gain",
        diet_type="non-veg",
        allergies=["peanuts"],
        excluded_foods=[],
    )


@pytest.fixture
def sample_targets(sample_veg_profile: UserProfile):
    return calculate_nutrition_targets(sample_veg_profile)


@pytest.fixture
def food_df() -> pd.DataFrame:
    return _get_df()
