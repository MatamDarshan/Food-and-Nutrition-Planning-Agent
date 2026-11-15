"""
ui/meal_planner.py
------------------
Page 3: Interactive 7-Day Indian Meal Planner with:
- Monday–Sunday day selection navigation.
- 4 meal cards per day (Breakfast, Lunch, Evening Snack, Dinner).
- Food-level nutrition and serving descriptions.
- Meal-level subtotals and daily totals.
- Estimated micronutrients (Vitamins & Minerals) with authentic IFCT provenance and RDA targets.
- Clear distinction between 0.0 intake and unavailable/unreported nutrient data.
- Weekly Summary with average metrics, daily calorie comparison charts, and compliance status.
"""

from typing import Any, Optional
import pandas as pd
import streamlit as st

from data.micronutrient_data import RDA_REFERENCE


MEAL_CONFIG = {
    "breakfast": {"icon": "🌅", "label": "Breakfast"},
    "lunch": {"icon": "🍛", "label": "Lunch"},
    "snack": {"icon": "☕", "label": "Evening Snack"},
    "dinner": {"icon": "🍽️", "label": "Dinner"},
}

DAYS_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def render_7day_meal_planner(
    weekly_plan: Optional[dict[str, Any]],
    targets: Optional[dict[str, Any]],
    validation_result: Optional[dict[str, Any]] = None,
) -> None:
    """Render the full 7-Day Meal Planner interface."""
    if not weekly_plan or not weekly_plan.get("days"):
        st.info("👈 Please enter your details on the **User Profile** page and click **'Generate My Nutrition Plan'** to generate your 7-day plan.")
        return

    days_data = weekly_plan.get("days", [])
    day_map = {d.get("day_name", ""): d for d in days_data}
    weekly_avg = weekly_plan.get("weekly_averages", {})
    t_cal = targets.get("calorie_target", 2000.0) if targets else 2000.0

    st.markdown("### 🍱 7-Day Personalized Indian Meal Plan")
    st.caption("Complete Monday through Sunday nutrition plan with authentic Indian food variety and ICMR-NIN verified nutrition.")

    # Validation banner
    val_status = weekly_plan.get("validation_result") or validation_result
    if val_status:
        is_valid = val_status.get("is_valid", True)
        issues = val_status.get("issues", [])
        if is_valid:
            st.markdown(
                """
                <div class="disclaimer-banner" style="background-color: #D8F3DC; border-color: #2D6A4F; color: #1B4332;">
                    <strong>✅ Plan Validated & 100% Compliant:</strong> All 7 days and 4 meals met. Zero allergen violations, zero dietary preference conflicts, and calories aligned within target.
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            issues_md = "<br>".join(f"• {i}" for i in issues)
            st.markdown(
                f"""
                <div class="disclaimer-banner" style="background-color: #FEF3C7; border-color: #D97706; color: #92400E;">
                    <strong>⚠️ Plan Advisory Notes:</strong><br>{issues_md}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Day selection navigation tabs + Weekly Summary tab
    tab_names = DAYS_ORDER + ["📊 Weekly Summary & Analytics"]
    tabs = st.tabs(tab_names)

    # Render each day (Monday - Sunday)
    for idx, day_name in enumerate(DAYS_ORDER):
        with tabs[idx]:
            day_info = day_map.get(day_name)
            if not day_info:
                st.warning(f"No meal data available for {day_name}.")
                continue

            meals = day_info.get("meals", {})
            d_cal = day_info.get("total_calories", 0.0)
            d_prot = day_info.get("total_protein", 0.0)
            d_carb = day_info.get("total_carbs", 0.0)
            d_fat = day_info.get("total_fat", 0.0)
            d_fib = day_info.get("total_fiber", 0.0)
            d_dev = day_info.get("calorie_deviation_pct", 0.0)

            st.markdown(f"#### 📅 {day_name}'s Menu")

            # 4 Meal Cards
            for slot_key in ["breakfast", "lunch", "snack", "dinner"]:
                meal_detail = meals.get(slot_key, {})
                cfg = MEAL_CONFIG.get(slot_key, {"icon": "🍽️", "label": slot_key.title()})
                m_label = cfg["label"]
                m_icon = cfg["icon"]
                items = meal_detail.get("items", [])

                with st.expander(f"{m_icon} **{m_label}** — {meal_detail.get('total_calories', 0):.0f} kcal", expanded=True):
                    if not items:
                        st.caption("No food items scheduled.")
                        continue

                    rows = []
                    for item in items:
                        rows.append({
                            "Food Item": item.get("food_name", ""),
                            "Category": item.get("food_category", "General"),
                            "Serving & Portion": item.get("serving_display", f"{item.get('quantity_g', 0):.0f} g"),
                            "Calories (kcal)": f"{item.get('calories', 0):.1f}",
                            "Protein (g)": f"{item.get('protein', 0):.1f}",
                            "Carbs (g)": f"{item.get('carbohydrates', 0):.1f}",
                            "Fats (g)": f"{item.get('fat', 0):.1f}",
                            "Fiber (g)": f"{item.get('fiber', 0):.1f}",
                        })

                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                    st.markdown(
                        f"""
                        <div class="meal-subtotal">
                            <strong>{m_label} Total:</strong> 🔥 <strong>{meal_detail.get('total_calories', 0):.0f} kcal</strong> |
                            🥩 <strong>{meal_detail.get('total_protein', 0):.1f}g Protein</strong> |
                            🌾 <strong>{meal_detail.get('total_carbs', 0):.1f}g Carbs</strong> |
                            🥑 <strong>{meal_detail.get('total_fat', 0):.1f}g Fats</strong> |
                            🥦 <strong>{meal_detail.get('total_fiber', 0):.1f}g Fiber</strong>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            # Daily Nutritional Summary Card
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"#### 📈 {day_name} Total Nutritional Summary")

            s1, s2, s3, s4, s5 = st.columns(5)
            with s1:
                st.metric("Total Calories", f"{d_cal:.0f} kcal", delta=f"{d_dev:+.1f}% vs goal")
            with s2:
                st.metric("Total Protein", f"{d_prot:.1f} g")
            with s3:
                st.metric("Total Carbohydrates", f"{d_carb:.1f} g")
            with s4:
                st.metric("Total Fats", f"{d_fat:.1f} g")
            with s5:
                st.metric("Dietary Fiber", f"{d_fib:.1f} g")

            # Estimated Micronutrients Section
            st.markdown("<br>", unsafe_allow_html=True)
            with st.expander(f"🔬 **{day_name} Estimated Micronutrients (Vitamins & Minerals)**", expanded=False):
                st.caption(
                    "Derived from authenticated ICMR-NIN Indian Food Composition Tables (IFCT 2017). "
                    "Values explicitly distinguish between tested zero values and unanalyzed/unavailable fields ('N/A')."
                )

                micros = day_info.get("micronutrients", {})

                # Minerals Table
                st.markdown("##### Essential Minerals")
                mineral_keys = ["calcium_mg", "iron_mg", "magnesium_mg", "potassium_mg", "zinc_mg", "sodium_mg"]
                min_rows = []
                for k in mineral_keys:
                    ref = RDA_REFERENCE.get(k, {})
                    label = ref.get("label", k)
                    unit = ref.get("unit", "")
                    target_val = ref.get("target", 0.0)
                    val = micros.get(k)
                    if val is None:
                        consumed_str = "Not Reported in IFCT"
                        coverage_str = "N/A"
                    else:
                        consumed_str = f"{val:.1f} {unit}"
                        pct = (val / target_val * 100) if target_val > 0 else 0
                        coverage_str = f"{pct:.0f}% of RDA"

                    min_rows.append({
                        "Mineral": label,
                        "Amount Consumed": consumed_str,
                        "Reference Target (RDA 2020)": f"{target_val:.0f} {unit}",
                        "RDA Coverage": coverage_str,
                    })
                st.dataframe(pd.DataFrame(min_rows), use_container_width=True, hide_index=True)

                # Vitamins Table
                st.markdown("##### Essential Vitamins")
                vit_keys = [
                    "vitamin_a_mcg", "vitamin_b1_mg", "vitamin_b2_mg", "vitamin_b3_mg",
                    "vitamin_b6_mg", "vitamin_b9_mcg", "vitamin_b12_mcg", "vitamin_c_mg",
                    "vitamin_d_mcg", "vitamin_e_mg", "vitamin_k_mcg"
                ]
                vit_rows = []
                for k in vit_keys:
                    ref = RDA_REFERENCE.get(k, {})
                    label = ref.get("label", k)
                    unit = ref.get("unit", "")
                    target_val = ref.get("target", 0.0)
                    val = micros.get(k)
                    if val is None:
                        consumed_str = "Not Reported in IFCT"
                        coverage_str = "N/A"
                    else:
                        consumed_str = f"{val:.1f} {unit}"
                        pct = (val / target_val * 100) if target_val > 0 else 0
                        coverage_str = f"{pct:.0f}% of RDA"

                    vit_rows.append({
                        "Vitamin": label,
                        "Amount Consumed": consumed_str,
                        "Reference Target (RDA 2020)": f"{target_val:.1f} {unit}",
                        "RDA Coverage": coverage_str,
                    })
                st.dataframe(pd.DataFrame(vit_rows), use_container_width=True, hide_index=True)

    # Weekly Summary & Analytics Tab
    with tabs[-1]:
        st.markdown("#### 📊 Weekly Summary & Analytics")

        # 5 Average KPI Cards
        avg_cal = weekly_avg.get("avg_calories", 0.0)
        avg_prot = weekly_avg.get("avg_protein", 0.0)
        avg_carb = weekly_avg.get("avg_carbs", 0.0)
        avg_fat = weekly_avg.get("avg_fat", 0.0)
        avg_fib = weekly_avg.get("avg_fiber", 0.0)

        w1, w2, w3, w4, w5 = st.columns(5)
        with w1:
            st.metric("Avg Daily Calories", f"{avg_cal:.0f} kcal", help=f"Target: {t_cal:.0f} kcal")
        with w2:
            st.metric("Avg Daily Protein", f"{avg_prot:.1f} g")
        with w3:
            st.metric("Avg Daily Carbs", f"{avg_carb:.1f} g")
        with w4:
            st.metric("Avg Daily Fat", f"{avg_fat:.1f} g")
        with w5:
            st.metric("Avg Daily Fiber", f"{avg_fib:.1f} g")

        st.divider()

        # Daily Calorie Comparison Chart
        st.markdown("##### 📈 Daily Calorie Comparison vs Target")
        daily_cals_dict = weekly_avg.get("daily_calories", {})
        if daily_cals_dict:
            cal_df = pd.DataFrame(
                [{"Day": day, "Planned Calories": daily_cals_dict.get(day, 0.0), "Target Calories": t_cal} for day in DAYS_ORDER]
            ).set_index("Day")
            st.bar_chart(cal_df[["Planned Calories", "Target Calories"]])

        # Weekly Macronutrient Distribution
        st.markdown("##### 🥗 Weekly Average Macronutrient Distribution (Grams)")
        macro_df = pd.DataFrame({
            "Nutrient": ["Protein", "Carbohydrates", "Fats", "Fiber"],
            "Average Grams/Day": [avg_prot, avg_carb, avg_fat, avg_fib],
        }).set_index("Nutrient")
        st.bar_chart(macro_df)

        # Target Compliance Note
        compliance = weekly_avg.get("calorie_compliance", True)
        if compliance:
            st.success(f"🎯 **Target Compliance Met:** Weekly average of {avg_cal:.0f} kcal is within ±15% of your target ({t_cal:.0f} kcal).")
        else:
            st.warning(f"⚠️ **Target Compliance Alert:** Weekly average of {avg_cal:.0f} kcal deviates beyond the ±15% threshold.")

        # Rationale & Scientific References
        rationale = weekly_plan.get("rationale")
        if rationale:
            st.markdown("##### 📝 AI Nutritionist Weekly Rationale")
            # Strip internal JSON blocks from the rationale text if any were appended
            clean_rationale = rationale
            if "```json" in clean_rationale:
                clean_rationale = clean_rationale.split("```json")[0] + clean_rationale.split("```")[-1]
            st.markdown(clean_rationale.strip())

        refs = weekly_plan.get("source_references", [])
        if refs:
            st.markdown("##### 📚 Authoritative Scientific References")
            for r in refs:
                st.markdown(f"- {r}")
