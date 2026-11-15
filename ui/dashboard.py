"""
ui/dashboard.py
---------------
Page 2: Modern Nutrition Dashboard with:
- Individual metric cards for:
  * BMI & BMI category
  * BMR (Mifflin-St Jeor)
  * TDEE (Maintenance)
  * Daily calorie target
  * Daily protein target
  * Daily carbohydrate target
  * Daily fat target
  * Dietary fibre target
- Visual charts:
  * Macronutrient distribution (calories & %)
  * Calorie target comparison (BMR vs TDEE vs Daily Target)
  * Protein, carbohydrate, fat, and fiber target breakdown (grams)
"""

from typing import Any, Optional
import pandas as pd
import streamlit as st


def render_nutrition_dashboard(
    targets: Optional[dict[str, Any]],
    meal_plan: Optional[dict[str, Any]] = None,
    validation_result: Optional[dict[str, Any]] = None,
) -> None:
    """Render the full nutrition KPI cards, target vs planned macros, and interactive charts."""
    if not targets:
        st.info("💡 Fill out your profile in the **User Profile** page and click **'Generate My Nutrition Plan'** to calculate targets.")
        return

    st.markdown("### 📊 Personalized Biometric & Nutrition Dashboard")
    st.caption("Energy requirements and macronutrient partitions derived from the Mifflin-St Jeor equation and ICMR-NIN nutritional standards.")

    # ── Section 1: Biometric & Caloric Metric Cards ─────────────────────────
    bmi_val = targets.get("bmi", 0.0)
    bmi_cat = targets.get("bmi_category", "Normal weight")
    bmr_val = targets.get("bmr", 0.0)
    tdee_val = targets.get("tdee", 0.0)
    cal_target = targets.get("calorie_target", 2000.0)

    # 4 Biometric Cards
    st.markdown("#### Biometric Energy Requirements")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(
            label="BMI (Body Mass Index)",
            value=f"{bmi_val:.1f} kg/m²",
            help="WHO / ICMR classification",
        )
        st.caption(f"Category: **{bmi_cat}**")
    with c2:
        st.metric(
            label="BMR (Mifflin-St Jeor)",
            value=f"{bmr_val:.0f} kcal",
            help="Basal Metabolic Rate: resting energy expenditure",
        )
        st.caption("Resting metabolic base")
    with c3:
        st.metric(
            label="TDEE (Maintenance)",
            value=f"{tdee_val:.0f} kcal",
            help="Total Daily Energy Expenditure based on Physical Activity Level (PAL)",
        )
        st.caption("Weight-maintenance baseline")
    with c4:
        st.metric(
            label="Daily Calorie Target",
            value=f"{cal_target:.0f} kcal",
            help="Target energy intake after goal adjustment (deficit/surplus)",
        )
        delta_cal = cal_target - tdee_val
        st.caption(f"Adjustment: **{delta_cal:+.0f} kcal vs TDEE**")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Section 2: Macronutrient Target Cards ───────────────────────────────
    t_prot = targets.get("protein_g", 0.0)
    t_carb = targets.get("carbs_g", 0.0)
    t_fat = targets.get("fats_g", 0.0)
    t_fib = targets.get("fiber_g", 0.0)

    st.markdown("#### Daily Macronutrient & Fibre Targets")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(
            label="Daily Protein Target",
            value=f"{t_prot:.1f} g",
            help="Target protein intake based on body weight and fitness goal",
        )
        prot_cals = t_prot * 4
        prot_pct = (prot_cals / cal_target * 100) if cal_target > 0 else 0
        st.caption(f"🔥 {prot_cals:.0f} kcal ({prot_pct:.0f}% of total energy)")

    with m2:
        st.metric(
            label="Daily Carbohydrate Target",
            value=f"{t_carb:.1f} g",
            help="Remaining daily energy after protein and essential fat allocation",
        )
        carb_cals = t_carb * 4
        carb_pct = (carb_cals / cal_target * 100) if cal_target > 0 else 0
        st.caption(f"🔥 {carb_cals:.0f} kcal ({carb_pct:.0f}% of total energy)")

    with m3:
        st.metric(
            label="Daily Fat Target",
            value=f"{t_fat:.1f} g",
            help="Essential healthy fats (approx. 27% of daily calories)",
        )
        fat_cals = t_fat * 9
        fat_pct = (fat_cals / cal_target * 100) if cal_target > 0 else 0
        st.caption(f"🔥 {fat_cals:.0f} kcal ({fat_pct:.0f}% of total energy)")

    with m4:
        st.metric(
            label="Daily Dietary Fibre Target",
            value=f"{t_fib:.1f} g",
            help="Standard reference of 14g per 1000 kcal intake",
        )
        st.caption("Essential for gut motility & satiety")

    st.divider()

    # ── Section 3: Visual Charts ─────────────────────────────────────────────
    st.markdown("#### 📈 Target Visualizations & Caloric Partitions")
    ch_col1, ch_col2 = st.columns(2)

    with ch_col1:
        st.markdown("##### Energy Math (BMR vs TDEE vs Target)")
        energy_df = pd.DataFrame({
            "Stage": ["1. BMR (Resting)", "2. TDEE (Maintenance)", "3. Calorie Target (Goal)"],
            "Calories (kcal/day)": [bmr_val, tdee_val, cal_target],
        }).set_index("Stage")
        st.bar_chart(energy_df)

    with ch_col2:
        st.markdown("##### Macronutrient Energy Contribution (kcal)")
        macro_split_df = pd.DataFrame({
            "Macronutrient": ["Protein (4 kcal/g)", "Carbohydrates (4 kcal/g)", "Fats (9 kcal/g)"],
            "Calories (kcal)": [t_prot * 4, t_carb * 4, t_fat * 9],
        }).set_index("Macronutrient")
        st.bar_chart(macro_split_df)

    st.markdown("##### Daily Target Quantities (Grams)")
    grams_df = pd.DataFrame({
        "Nutrient": ["Protein", "Carbohydrates", "Fats", "Dietary Fibre"],
        "Target Grams": [t_prot, t_carb, t_fat, t_fib],
    }).set_index("Nutrient")
    st.bar_chart(grams_df)

    st.divider()

    # ── Section 4: Scientific Guidance Context ──────────────────────────────
    st.markdown(
        """
        <div class="custom-card">
            <div class="card-header">
                <span>📚 Scientific Formulation Methodology</span>
            </div>
            <p style="font-size: 0.9rem; color: #4B5563; line-height: 1.5;">
                • <strong>BMR Calculation:</strong> Computed via the gold-standard <em>Mifflin-St Jeor</em> formula, validated to be within 10% of true resting energy expenditure.<br>
                • <strong>Activity Multipliers:</strong> PAL factors scale from 1.2 (Sedentary) up to 1.9 (Extra Active) following WHO/ICMR standards.<br>
                • <strong>Macronutrient Distribution:</strong> Protein is tailored to your fitness goal (1.0–2.0 g/kg body weight), healthy fats are set at ~27% of energy for endocrine and lipid function, and unrefined carbohydrates supply the remaining energy.<br>
                • <strong>Dietary Fibre:</strong> Calculated at 14 g per 1000 kcal intake to support healthy postprandial glucose regulation.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
