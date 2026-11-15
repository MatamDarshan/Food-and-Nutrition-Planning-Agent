"""
ui/profile_form.py
------------------
Streamlit form component for capturing and validating user profile data.
"""

from typing import Any, Optional
import streamlit as st
from core.user_profile import UserProfile


ACTIVITY_OPTIONS = {
    "sedentary": "Sedentary (desk job, minimal exercise)",
    "lightly_active": "Lightly Active (light exercise 1–3 days/wk)",
    "moderately_active": "Moderately Active (moderate exercise 3–5 days/wk)",
    "very_active": "Very Active (hard exercise 6–7 days/wk)",
    "extra_active": "Extra Active (physical labor or twice-a-day training)",
}

GOAL_OPTIONS = {
    "weight_loss": "Weight Loss (500 kcal deficit)",
    "maintenance": "Maintenance (stay at current weight)",
    "muscle_gain": "Muscle Gain (300 kcal lean bulk surplus)",
}

ALLERGEN_LIST = [
    "gluten",
    "dairy",
    "eggs",
    "fish",
    "tree_nuts",
    "peanuts",
    "soy",
    "shellfish",
]


def render_profile_form() -> Optional[dict[str, Any]]:
    """Render the user profile input form and return validated profile dict if submitted."""
    st.markdown("### 👤 User Profile & Goals")
    st.caption("Enter your biometric and dietary details to calculate nutritional targets.")

    with st.form("user_profile_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name", value="Arjun", placeholder="Enter your name")
            age = st.number_input("Age (years)", min_value=10, max_value=100, value=28, step=1)
            gender = st.selectbox("Gender", options=["male", "female"], index=0)

        with col2:
            height_cm = st.number_input(
                "Height (cm)", min_value=100.0, max_value=250.0, value=175.0, step=0.5
            )
            weight_kg = st.number_input(
                "Weight (kg)", min_value=30.0, max_value=250.0, value=75.0, step=0.5
            )
            diet_type = st.radio(
                "Dietary Preference", options=["veg", "non-veg"], horizontal=True, index=0
            )

        activity_level = st.selectbox(
            "Physical Activity Level",
            options=list(ACTIVITY_OPTIONS.keys()),
            format_func=lambda k: ACTIVITY_OPTIONS[k],
            index=2,
        )

        fitness_goal = st.selectbox(
            "Fitness Goal",
            options=list(GOAL_OPTIONS.keys()),
            format_func=lambda k: GOAL_OPTIONS[k],
            index=0,
        )

        allergies = st.multiselect(
            "Food Allergies to Exclude",
            options=ALLERGEN_LIST,
            default=[],
            help="Select any allergen tags you must strictly avoid.",
        )

        excluded_input = st.text_input(
            "Excluded Foods (comma-separated)",
            value="",
            placeholder="e.g. Samosa, Bhel Puri, Sugar",
            help="Specific foods you do not want in your meal plan.",
        )

        submitted = st.form_submit_button("🚀 Generate Personalized Meal Plan", use_container_width=True)

        if submitted:
            excluded_list = [f.strip() for f in excluded_input.split(",") if f.strip()]
            try:
                profile_obj = UserProfile(
                    name=name.strip(),
                    age=int(age),
                    gender=gender,
                    height_cm=float(height_cm),
                    weight_kg=float(weight_kg),
                    activity_level=activity_level,
                    fitness_goal=fitness_goal,
                    diet_type=diet_type,
                    allergies=allergies,
                    excluded_foods=excluded_list,
                )
                st.success("✅ Profile successfully validated!")
                return profile_obj.model_dump()
            except Exception as e:
                st.error(f"❌ Profile Validation Error: {e}")
                return None

    return None
