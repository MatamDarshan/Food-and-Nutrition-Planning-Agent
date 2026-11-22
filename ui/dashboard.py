"""
ui/dashboard.py
---------------
The "your numbers" dashboard shown under the profile form.

All values are supplied by the existing ``calculate_nutrition_targets`` backend.
This module only presents BMI, BMR/RMR, TDEE, calorie and macro targets with
colour-coded cards, a distribution chart and a short methodology explainer.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

from ui.components import (
    callout,
    metric_card,
    progress_bar,
    render_badges,
    section_header,
    stat_tile,
)
from ui.layout import render_page_header


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bmi_tone(category: str) -> str:
    text = str(category).lower()
    if "normal" in text or "healthy" in text:
        return "green"
    if "under" in text:
        return "amber"
    if "over" in text:
        return "orange"
    if "obes" in text:
        return "red"
    return "blue"


def render_targets_panel(
    targets: Optional[dict[str, Any]],
    user_profile: Optional[dict[str, Any]] = None,
) -> None:
    """Show BMI, BMR, TDEE and daily targets as a polished dashboard."""
    if not targets:
        callout("Fill in the profile above to calculate your calorie and macro targets.", tone="blue")
        return

    bmi = _num(targets.get("bmi"))
    bmi_category = str(targets.get("bmi_category", "Unknown"))
    bmr = _num(targets.get("bmr"))
    tdee = _num(targets.get("tdee"))
    calorie = _num(targets.get("calorie_target"), 2000.0)
    protein = _num(targets.get("protein_g"))
    carbs = _num(targets.get("carbs_g"))
    fats = _num(targets.get("fats_g"))
    fibre = _num(targets.get("fiber_g"))

    render_page_header(
        "Your calculated numbers",
        subtitle="These targets come from your age, body measurements, activity level and goal.",
        icon="📊",
        level=3,
        badges=[
            {"label": f"BMI category: {bmi_category}", "tone": _bmi_tone(bmi_category), "icon": "📏"},
            {"label": f"{calorie:,.0f} kcal/day", "tone": "orange", "icon": "🔥"},
        ],
    )

    section_header("Energy baseline", icon="⚡", level=5)
    columns = st.columns(4)
    with columns[0]:
        metric_card("BMI", f"{bmi:.1f}", tone=_bmi_tone(bmi_category))
        st.caption(bmi_category)
    with columns[1]:
        metric_card("BMR / RMR (kcal)", f"{bmr:,.0f}", tone="teal")
        st.caption("Energy at rest")
    with columns[2]:
        metric_card("TDEE (kcal)", f"{tdee:,.0f}", tone="blue")
        st.caption("Maintenance needs")
    with columns[3]:
        metric_card("Daily target (kcal)", f"{calorie:,.0f}", tone="orange")
        st.caption(f"{calorie - tdee:+,.0f} vs maintenance")

    section_header("Daily macro targets", icon="🥗", level=5)
    macro_columns = st.columns(4)
    macro_specs = [
        ("Protein", protein, "protein", "g", "4 kcal per gram"),
        ("Carbohydrates", carbs, "carbs", "g", "4 kcal per gram"),
        ("Fats", fats, "fats", "g", "9 kcal per gram"),
        ("Fibre", fibre, "fibre", "g", "14 g per 1,000 kcal"),
    ]
    for column, (label, value, tone, unit, hint) in zip(macro_columns, macro_specs):
        with column:
            stat_tile(label, f"{value:.0f} {unit}", tone=tone, hint=hint)
            progress_bar(
                label=f"{label} target",
                current=value,
                target=value or 1.0,
                tone=tone,
                show_pct=False,
            )

    with st.expander("📈 Energy distribution of your daily target"):
        energy = pd.DataFrame(
            {
                "Macro": ["Protein", "Carbohydrates", "Fats"],
                "Calories from target": [
                    protein * 4,
                    carbs * 4,
                    fats * 9,
                ],
            }
        ).set_index("Macro")
        st.bar_chart(
            energy,
            alt="Calorie contribution from protein, carbohydrates and fat targets",
        )
        st.caption(
            "This chart splits your macro targets into their energy values. "
            "Small differences from the calorie target are expected because "
            "fibre and rounding are handled separately by the planner."
        )

    with st.expander("📚 How these numbers are calculated"):
        st.markdown(
            "- **BMI:** weight ÷ height².\n"
            "- **BMR / RMR:** Mifflin–St Jeor equation.\n"
            "- **TDEE:** BMR × activity multiplier (1.2 sedentary → 1.9 extra active).\n"
            "- **Calories:** TDEE adjusted for your goal (−500 for weight loss, "
            "+300 for muscle gain).\n"
            "- **Protein:** 1.0–2.0 g per kg of body weight, based on your goal.\n"
            "- **Fats:** about 27% of daily energy; **carbs** take the rest.\n"
            "- **Fibre:** 14 g per 1,000 kcal."
        )
        render_badges(
            [
                {"label": "Calculated locally", "tone": "green", "icon": "🔒"},
                {"label": "No medical claims", "tone": "blue", "icon": "ℹ️"},
            ]
        )


def render_nutrition_dashboard(
    targets: Optional[dict[str, Any]],
    meal_plan: Optional[dict[str, Any]] = None,
    weekly_plan: Optional[dict[str, Any]] = None,
    validation_result: Optional[dict[str, Any]] = None,
    user_name: str = "User",
) -> None:
    """Backwards-compatible alias for older callers."""
    render_targets_panel(targets)


__all__ = ["render_nutrition_dashboard", "render_targets_panel"]
