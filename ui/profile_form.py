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
    st.markdown(
        """
        <div class="disclaimer-banner">
            <strong>⚠️ Educational Use Notice:</strong> This application is designed for healthy adults (18+).
            Calculations use the Mifflin-St Jeor equation and ICMR-NIN nutritional standards.
            It does not constitute clinical medical therapy. Consult a physician for specialized medical conditions.
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("user_profile_form", clear_on_submit=False):
        # Section 1: Personal Details
        st.markdown("#### 1. Personal Details")
        c1, c2, c3 = st.columns(3)
        with c1:
            name = st.text_input("Full Name", value="Arjun", placeholder="Enter your name")
        with c2:
            age = st.number_input("Age (years, 18+)", min_value=18, max_value=100, value=28, step=1, help="Must be an adult aged 18 or above")
        with c3:
            gender = st.selectbox("Biological Gender", options=["male", "female"], index=0, help="Used for Mifflin-St Jeor metabolic rate formula")

        st.divider()

        # Section 2: Biometrics & Activity
        st.markdown("#### 2. Biometrics & Activity Level")
        c4, c5, c6 = st.columns(3)
        with c4:
            height_cm = st.number_input(
                "Height (cm)", min_value=100.0, max_value=250.0, value=175.0, step=0.5
            )
        with c5:
            weight_kg = st.number_input(
                "Weight (kg)", min_value=30.0, max_value=250.0, value=75.0, step=0.5
            )
        with c6:
            activity_level = st.selectbox(
                "Physical Activity Level",
                options=list(ACTIVITY_OPTIONS.keys()),
                format_func=lambda k: ACTIVITY_OPTIONS[k],
                index=2,
            )

        st.divider()

        # Section 3: Dietary Preference & Fitness Goal
        st.markdown("#### 3. Dietary Preference & Fitness Goal")
        c7, c8 = st.columns(2)
        with c7:
            diet_type = st.radio(
                "Dietary Preference",
                options=["veg", "non-veg"],
                format_func=lambda x: "Vegetarian (Plant & Dairy)" if x == "veg" else "Non-Vegetarian (Eggs, Poultry, Fish & Meat)",
                horizontal=False,
                index=0,
            )
        with c8:
            fitness_goal = st.selectbox(
                "Primary Fitness Goal",
                options=list(GOAL_OPTIONS.keys()),
                format_func=lambda k: GOAL_OPTIONS[k],
                index=0,
            )

        st.divider()

        # Section 4: Allergies & Excluded Foods
        st.markdown("#### 4. Allergies & Food Exclusions")
        c9, c10 = st.columns(2)
        with c9:
            allergies = st.multiselect(
                "Food Allergies (Strict Exclusion)",
                options=ALLERGEN_LIST,
                default=[],
                help="Zero items containing these allergens will be allowed in the meal plan.",
            )
        with c10:
            excluded_input = st.text_input(
                "Specific Foods to Avoid (Comma-separated)",
                value="",
                placeholder="e.g. Samosa, Bhel Puri, Sugar",
                help="Enter any specific foods you dislike or want omitted.",
            )

        st.markdown("<br>", unsafe_allow_html=True)
        submitted = st.form_submit_button("🌿 Generate My Nutrition Plan", use_container_width=True)

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
                st.success("✅ Profile validated! Generating your personalized plan...")
                return profile_obj.model_dump()
            except Exception as e:
                st.error(f"❌ Profile Validation Error: {e}")
                return None

    return None
