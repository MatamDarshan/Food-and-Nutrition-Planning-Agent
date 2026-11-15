"""
ui/dashboard.py
---------------
Interactive Streamlit dashboard displaying calculated nutrition targets,
macro distributions, meal-by-meal plans, and validation results.
"""

from typing import Any, Optional
import pandas as pd
import streamlit as st
from tools.food_tools import _get_df


MEAL_CONFIG = {
    "breakfast": {"icon": "🌅", "label": "Breakfast"},
    "lunch": {"icon": "🍛", "label": "Lunch"},
    "snack": {"icon": "☕", "label": "Evening Snack"},
    "dinner": {"icon": "🍽️", "label": "Dinner"},
}


def render_nutrition_dashboard(
    targets: dict[str, Any],
    meal_plan: Optional[dict[str, Any]] = None,
    validation_result: Optional[dict[str, Any]] = None,
) -> None:
    """Render the full nutrition KPI cards, target vs planned macros, and meal tables."""
    if not targets:
        st.info("💡 Fill out the profile form and click 'Generate Meal Plan' to calculate targets.")
        return

    # ── Section 1: Biometric & Calorie Target Cards ─────────────────────────
    st.markdown("### 📊 Nutritional Targets")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="BMI",
            value=f"{targets.get('bmi', 0):.1f}",
            help=f"Category: {targets.get('bmi_category', 'Normal')}",
        )
        st.caption(f"**{targets.get('bmi_category', 'Normal')}**")
    with c2:
        st.metric(
            label="BMR (Mifflin-St Jeor)",
            value=f"{targets.get('bmr', 0):.0f} kcal",
            help="Basal Metabolic Rate at complete rest",
        )
    with c3:
        st.metric(
            label="TDEE (Maintenance)",
            value=f"{targets.get('tdee', 0):.0f} kcal",
            help="Total Daily Energy Expenditure based on activity level",
        )
    with c4:
        st.metric(
            label="Daily Calorie Goal",
            value=f"{targets.get('calorie_target', 0):.0f} kcal",
            help="Target calories after fitness-goal adjustment",
        )

    st.divider()

    # ── Section 2: Macronutrient Breakdown ──────────────────────────────────
    st.markdown("### 🥗 Macronutrient Breakdown")
    m1, m2, m3, m4 = st.columns(4)

    target_cal = targets.get("calorie_target", 2000.0)
    planned_cal = validation_result.get("planned_calories") if validation_result else None

    # Macro targets
    t_prot = targets.get("protein_g", 0.0)
    t_carb = targets.get("carbs_g", 0.0)
    t_fat = targets.get("fats_g", 0.0)
    t_fib = targets.get("fiber_g", 0.0)

    # Planned macros (if available)
    p_prot = validation_result.get("planned_protein") if validation_result else None
    p_carb = validation_result.get("planned_carbs") if validation_result else None
    p_fat = validation_result.get("planned_fats") if validation_result else None

    with m1:
        st.metric(
            label="Protein",
            value=f"{p_prot:.1f} g" if p_prot is not None else f"{t_prot:.1f} g",
            delta=f"{p_prot - t_prot:+.1f} g vs target" if p_prot is not None else None,
            help=f"Target: {t_prot:.1f} g",
        )
        if target_cal > 0:
            st.caption(f"Target: {t_prot:.1f} g")

    with m2:
        st.metric(
            label="Carbohydrates",
            value=f"{p_carb:.1f} g" if p_carb is not None else f"{t_carb:.1f} g",
            delta=f"{p_carb - t_carb:+.1f} g vs target" if p_carb is not None else None,
            help=f"Target: {t_carb:.1f} g",
        )
        if target_cal > 0:
            st.caption(f"Target: {t_carb:.1f} g")

    with m3:
        st.metric(
            label="Fats",
            value=f"{p_fat:.1f} g" if p_fat is not None else f"{t_fat:.1f} g",
            delta=f"{p_fat - t_fat:+.1f} g vs target" if p_fat is not None else None,
            help=f"Target: {t_fat:.1f} g",
        )
        if target_cal > 0:
            st.caption(f"Target: {t_fat:.1f} g")

    with m4:
        st.metric(
            label="Dietary Fiber",
            value=f"{t_fib:.1f} g",
            help="Recommended intake based on 14g per 1000 kcal",
        )
        st.caption("Target based on US DRI")

    st.divider()

    # ── Section 3: Validation Status ─────────────────────────────────────────
    if validation_result:
        is_valid = validation_result.get("is_valid", False)
        dev = validation_result.get("calorie_deviation_pct", 0.0)
        p_cal = validation_result.get("planned_calories", 0.0)
        t_cal = validation_result.get("target_calories", target_cal)

        if is_valid:
            st.success(
                f"✅ **Meal Plan Validated & Compliant** — Total Planned: **{p_cal:.0f} kcal** "
                f"(Target: {t_cal:.0f} kcal, deviation: **{dev:+.1f}%**). "
                f"All dietary, allergen, and meal constraints met."
            )
        else:
            issues = validation_result.get("issues", [])
            issues_md = "\n".join(f"- {i}" for i in issues)
            st.warning(
                f"⚠️ **Advisory Notes on Meal Plan** (Planned: **{p_cal:.0f} kcal** / "
                f"Target: {t_cal:.0f} kcal, deviation: {dev:+.1f}%):\n{issues_md}"
            )

    # ── Section 4: Meal Plan Display ─────────────────────────────────────────
    if meal_plan:
        st.markdown("### 🍱 Personalized 1-Day Indian Meal Plan")
        df_food = _get_df()
        name_index = df_food.set_index("food_name").to_dict(orient="index")

        meal_calories: dict[str, float] = {}

        for slot_key, slot_cfg in MEAL_CONFIG.items():
            items = meal_plan.get(slot_key, [])
            icon = slot_cfg["icon"]
            label = slot_cfg["label"]

            with st.expander(f"{icon} **{label}** ({len(items)} items)", expanded=True):
                if not items:
                    st.caption("No items in this meal slot.")
                    continue

                table_rows = []
                slot_total_cal = 0.0
                slot_total_prot = 0.0
                slot_total_carb = 0.0
                slot_total_fat = 0.0
                slot_total_fib = 0.0

                for item in items:
                    fname = item.get("food_name", "")
                    qty = float(item.get("quantity_g", 0))
                    info = name_index.get(fname, {})
                    scale = qty / 100.0 if qty > 0 else 0.0

                    cal = round(info.get("calories", 0.0) * scale, 1)
                    prot = round(info.get("protein", 0.0) * scale, 1)
                    carb = round(info.get("carbohydrates", 0.0) * scale, 1)
                    fat = round(info.get("fats", 0.0) * scale, 1)
                    fib = round(info.get("fiber", 0.0) * scale, 1)

                    slot_total_cal += cal
                    slot_total_prot += prot
                    slot_total_carb += carb
                    slot_total_fat += fat
                    slot_total_fib += fib

                    table_rows.append({
                        "Food Item": fname,
                        "Category": info.get("food_category", "-"),
                        "Quantity": f"{qty:.0f} g",
                        "Calories (kcal)": cal,
                        "Protein (g)": prot,
                        "Carbs (g)": carb,
                        "Fats (g)": fat,
                        "Fiber (g)": fib,
                        "Diet": info.get("diet_type", "-"),
                    })

                meal_calories[label] = slot_total_cal
                st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

                st.markdown(
                    f"**{label} Subtotals:** 🔥 **{slot_total_cal:.0f} kcal** | "
                    f"🥩 **{slot_total_prot:.1f}g Protein** | "
                    f"🌾 **{slot_total_carb:.1f}g Carbs** | "
                    f"🥑 **{slot_total_fat:.1f}g Fats** | "
                    f"🥦 **{slot_total_fib:.1f}g Fiber**"
                )

        # Meal Calorie Distribution Chart
        if meal_calories and sum(meal_calories.values()) > 0:
            st.markdown("#### 🥧 Calorie Distribution by Meal")
            dist_df = pd.DataFrame(
                list(meal_calories.items()), columns=["Meal", "Calories (kcal)"]
            ).set_index("Meal")
            st.bar_chart(dist_df)
