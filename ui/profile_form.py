"""
ui/profile_form.py
------------------
Polished profile creation and editing for NutriPlan.

The form keeps the original token-based widget recreation strategy.  Whenever a
preset, a blank form or a profile switch changes the draft, ``profile_form_token``
is bumped so Streamlit rebuilds every field with the new values instead of
showing stale widget state.
"""

from __future__ import annotations

from typing import Any, Optional

import streamlit as st

from core.user_profile import UserProfile
from ui.components import bmi_indicator, render_badges, section_header
from ui.layout import render_page_header


ACTIVITY_OPTIONS = {
    "sedentary": "Sedentary",
    "lightly_active": "Lightly active",
    "moderately_active": "Moderately active",
    "very_active": "Very active",
    "extra_active": "Extra active",
}

ACTIVITY_HELP = (
    "Sedentary: desk job, little movement.\n"
    "Lightly active: exercise 1–3 days a week.\n"
    "Moderately active: exercise 3–5 days a week.\n"
    "Very active: hard exercise 6–7 days a week.\n"
    "Extra active: physical job or training twice a day."
)

GOAL_OPTIONS = {
    "weight_loss": "Lose weight (−500 kcal)",
    "maintenance": "Maintain weight",
    "muscle_gain": "Gain muscle (+300 kcal)",
}

ALLERGEN_LABELS = {
    "gluten": "Gluten",
    "dairy": "Dairy",
    "eggs": "Eggs",
    "fish": "Fish",
    "tree_nuts": "Tree nuts",
    "peanuts": "Peanuts",
    "soy": "Soy",
    "shellfish": "Shellfish",
}

PRESET_PROFILES = {
    "Arjun (veg, weight loss)": {
        "name": "Arjun",
        "age": 28,
        "gender": "male",
        "height_cm": 175.0,
        "weight_kg": 75.0,
        "activity_level": "moderately_active",
        "fitness_goal": "weight_loss",
        "diet_type": "veg",
        "allergies": [],
        "excluded_foods": [],
    },
    "Priya (veg, maintain)": {
        "name": "Priya",
        "age": 25,
        "gender": "female",
        "height_cm": 162.0,
        "weight_kg": 56.0,
        "activity_level": "lightly_active",
        "fitness_goal": "maintenance",
        "diet_type": "veg",
        "allergies": [],
        "excluded_foods": [],
    },
    "Vikram (non-veg, muscle)": {
        "name": "Vikram",
        "age": 31,
        "gender": "male",
        "height_cm": 180.0,
        "weight_kg": 78.0,
        "activity_level": "very_active",
        "fitness_goal": "muscle_gain",
        "diet_type": "non-veg",
        "allergies": [],
        "excluded_foods": [],
    },
    "Sneha (veg, nut allergy)": {
        "name": "Sneha",
        "age": 24,
        "gender": "female",
        "height_cm": 165.0,
        "weight_kg": 60.0,
        "activity_level": "moderately_active",
        "fitness_goal": "weight_loss",
        "diet_type": "veg",
        "allergies": ["peanuts", "tree_nuts"],
        "excluded_foods": ["Samosa"],
    },
}


def blank_profile() -> dict[str, Any]:
    """Return an empty draft for a brand-new user."""
    return {
        "name": "",
        "age": 25,
        "gender": "male",
        "height_cm": 170.0,
        "weight_kg": 65.0,
        "activity_level": "moderately_active",
        "fitness_goal": "maintenance",
        "diet_type": "veg",
        "allergies": [],
        "excluded_foods": [],
    }


def _form_token() -> int:
    return int(st.session_state.get("profile_form_token", 0))


def _set_draft(draft: dict[str, Any]) -> None:
    """Replace the draft and force all form widgets to be re-created."""
    st.session_state.form_draft = dict(draft)
    st.session_state.profile_form_token = _form_token() + 1
    st.session_state._new_user_mode = True
    st.session_state._form_draft_user = None


def _draft(initial_profile: Optional[dict[str, Any]]) -> dict[str, Any]:
    if "form_draft" not in st.session_state:
        st.session_state.form_draft = dict(initial_profile or blank_profile())
    return st.session_state.form_draft


def _render_presets() -> None:
    """Render quick-start presets that fill every field at once."""
    section_header(
        "Quick start presets",
        subtitle="Pick an example, then edit anything before saving. Nothing is saved until you submit.",
        icon="✨",
        level=5,
    )
    preset_cols = st.columns(len(PRESET_PROFILES) + 1)
    for index, (label, preset) in enumerate(PRESET_PROFILES.items()):
        with preset_cols[index]:
            st.button(
                label,
                key=f"preset_btn_{index}",
                width="stretch",
                on_click=_set_draft,
                args=(preset,),
            )
    with preset_cols[-1]:
        st.button(
            "Blank form",
            key="blank_preset_btn",
            width="stretch",
            on_click=_set_draft,
            args=(blank_profile(),),
        )
    render_badges(
        [
            {"label": "All fields included", "tone": "green", "icon": "✓"},
            {"label": "Fully editable", "tone": "blue", "icon": "✏️"},
        ]
    )


def render_profile_form(
    initial_profile: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    """Render the profile form. Returns validated profile data on submit."""
    render_page_header(
        "My profile",
        subtitle="Your details drive every calorie, macro and meal suggestion. "
        "Saving a profile builds a fresh 7-day plan.",
        icon="👤",
        badges=[
            {"label": "Multiple profiles", "tone": "blue", "icon": "👥"},
            {"label": "ICMR-NIN informed", "tone": "green", "icon": "🌿"},
        ],
    )

    draft = _draft(initial_profile)
    token = _form_token()
    _render_presets()

    with st.form(f"user_profile_form_{token}", clear_on_submit=False):
        left, right = st.columns([1, 1], gap="large")

        with left:
            section_header("About you", icon="🙋", level=5)
            name_col, age_col = st.columns([2, 1])
            with name_col:
                name = st.text_input(
                    "Name *",
                    value=str(draft.get("name", "")),
                    placeholder="Type a name, e.g. Darshan",
                    key=f"pf_name_{token}",
                )
            with age_col:
                age = st.number_input(
                    "Age *",
                    min_value=18,
                    max_value=100,
                    value=int(draft.get("age", 25)),
                    step=1,
                    key=f"pf_age_{token}",
                )
            gender = st.selectbox(
                "Gender *",
                options=["male", "female"],
                index=0 if draft.get("gender", "male") == "male" else 1,
                format_func=lambda value: "Male" if value == "male" else "Female",
                key=f"pf_gender_{token}",
            )

            section_header("Body & activity", icon="📏", level=5)
            height_col, weight_col = st.columns(2)
            with height_col:
                height_cm = st.number_input(
                    "Height (cm) *",
                    min_value=100.0,
                    max_value=250.0,
                    value=float(draft.get("height_cm", 170.0)),
                    step=0.5,
                    key=f"pf_height_{token}",
                )
            with weight_col:
                weight_kg = st.number_input(
                    "Weight (kg) *",
                    min_value=25.0,
                    max_value=300.0,
                    value=float(draft.get("weight_kg", 65.0)),
                    step=0.5,
                    key=f"pf_weight_{token}",
                )

            activity_keys = list(ACTIVITY_OPTIONS.keys())
            current_activity = draft.get("activity_level", "moderately_active")
            activity_level = st.selectbox(
                "Activity level *",
                options=activity_keys,
                index=(
                    activity_keys.index(current_activity)
                    if current_activity in activity_keys
                    else 2
                ),
                format_func=lambda key: ACTIVITY_OPTIONS[key],
                help=ACTIVITY_HELP,
                key=f"pf_activity_{token}",
            )
            if height_cm > 0 and weight_kg > 0:
                bmi_indicator(weight_kg / ((height_cm / 100.0) ** 2))

        with right:
            section_header("Food & goals", icon="🎯", level=5)
            diet_col, goal_col = st.columns(2)
            with diet_col:
                diet_type = st.radio(
                    "Diet *",
                    options=["veg", "non-veg"],
                    index=0 if draft.get("diet_type", "veg") == "veg" else 1,
                    format_func=lambda value: (
                        "🌱 Vegetarian" if value == "veg" else "🍗 Non-vegetarian"
                    ),
                    horizontal=True,
                    key=f"pf_diet_{token}",
                )
            with goal_col:
                goal_keys = list(GOAL_OPTIONS.keys())
                current_goal = draft.get("fitness_goal", "maintenance")
                fitness_goal = st.selectbox(
                    "Goal *",
                    options=goal_keys,
                    index=goal_keys.index(current_goal) if current_goal in goal_keys else 1,
                    format_func=lambda key: GOAL_OPTIONS[key],
                    key=f"pf_goal_{token}",
                )

            allergies = st.multiselect(
                "Allergies (foods to avoid completely)",
                options=list(ALLERGEN_LABELS.keys()),
                default=[
                    allergen
                    for allergen in draft.get("allergies", [])
                    if allergen in ALLERGEN_LABELS
                ],
                format_func=lambda key: ALLERGEN_LABELS.get(key, key),
                key=f"pf_allergies_{token}",
            )
            excluded_input = st.text_input(
                "Other foods you dislike (optional, comma separated)",
                value=", ".join(str(food) for food in draft.get("excluded_foods", [])),
                placeholder="e.g. Samosa, Sugar",
                key=f"pf_excluded_{token}",
            )
            render_badges(
                [
                    {"label": "Allergy-safe planning", "tone": "red", "icon": "⚠️"},
                    {"label": "Excluded foods respected", "tone": "amber", "icon": "🚫"},
                ]
            )

        st.write("")
        submitted = st.form_submit_button(
            "💾 Save profile & build my plan",
            type="primary",
            width="stretch",
        )

        if submitted:
            clean_name = name.strip() if name else ""
            if not clean_name:
                st.error("Please type a name first — every profile needs one.")
                return None

            try:
                profile = UserProfile(
                    name=clean_name,
                    age=int(age),
                    gender=gender,
                    height_cm=float(height_cm),
                    weight_kg=float(weight_kg),
                    activity_level=activity_level,
                    fitness_goal=fitness_goal,
                    diet_type=diet_type,
                    allergies=allergies,
                    excluded_foods=[
                        food.strip()
                        for food in excluded_input.split(",")
                        if food.strip()
                    ],
                )
            except Exception as exc:
                st.error(f"Something in those details isn't valid: {exc}")
                return None

            profile_data = profile.model_dump()
            st.session_state.form_draft = dict(profile_data)
            return profile_data

    return None


__all__ = [
    "ACTIVITY_OPTIONS",
    "ALLERGEN_LABELS",
    "GOAL_OPTIONS",
    "PRESET_PROFILES",
    "blank_profile",
    "render_profile_form",
]
