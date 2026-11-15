"""
ui/food_database.py
-------------------
Page 4: Redesigned Indian Food Database Explorer:
- Real-time search by food name.
- Filter by diet type (Vegetarian / Non-Vegetarian).
- Filter by food category.
- Detailed nutritional values per 100 g (Calories, Protein, Carbs, Fats, Fiber, GI).
- Detailed vitamins & minerals lookup with authentic ICMR-NIN IFCT provenance.
- Clear allergen tags.
"""

from typing import Any
import pandas as pd
import streamlit as st

from data.micronutrient_data import MICRONUTRIENTS_PER_100G, RDA_REFERENCE, HOUSEHOLD_SERVINGS
from tools.food_tools import _get_df


def render_food_database_page() -> None:
    """Render the redesigned Food Database Explorer page."""
    st.markdown("### 🔍 Indian Food Composition Database")
    st.caption("Authenticated nutritional metrics per 100g edible portion from the ICMR-National Institute of Nutrition (NIN) IFCT 2017.")

    df_all = _get_df()

    # Search & Filters
    f1, f2, f3 = st.columns(3)
    with f1:
        search_query = st.text_input("🔍 Search Food Name", placeholder="e.g. Idli, Paneer, Dal, Chicken...")
    with f2:
        diet_filter = st.selectbox(
            "Dietary Category",
            options=["All", "Vegetarian", "Non-Vegetarian"],
            index=0,
        )
    with f3:
        all_categories = sorted(df_all["food_category"].unique().tolist())
        cat_filter = st.selectbox(
            "Food Group / Category",
            options=["All"] + all_categories,
            index=0,
        )

    # Filter dataframe
    filtered_df = df_all.copy()
    if search_query:
        filtered_df = filtered_df[filtered_df["food_name"].str.contains(search_query, case=False, na=False)]
    if diet_filter == "Vegetarian":
        filtered_df = filtered_df[filtered_df["diet_type"] == "veg"]
    elif diet_filter == "Non-Vegetarian":
        filtered_df = filtered_df[filtered_df["diet_type"] == "non-veg"]

    if cat_filter != "All":
        filtered_df = filtered_df[filtered_df["food_category"] == cat_filter]

    st.caption(f"Showing **{len(filtered_df)}** of **{len(df_all)}** authenticated Indian food items.")

    # Main Overview Table
    display_cols = [
        "food_name", "food_category", "diet_type", "calories",
        "protein", "carbohydrates", "fats", "fiber", "glycemic_index", "allergens"
    ]
    renamed_cols = {
        "food_name": "Food Name",
        "food_category": "Category",
        "diet_type": "Diet Type",
        "calories": "Calories (kcal)",
        "protein": "Protein (g)",
        "carbohydrates": "Carbs (g)",
        "fats": "Fats (g)",
        "fiber": "Fiber (g)",
        "glycemic_index": "Glycemic Index",
        "allergens": "Allergen Tags",
    }
    view_df = filtered_df[display_cols].rename(columns=renamed_cols)
    st.dataframe(view_df, use_container_width=True, hide_index=True)

    # Food Detail Inspector for Micronutrients & Servings
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🔬 Detailed Micronutrient & Portion Inspector")
    st.caption("Select any food item below to inspect its authentic vitamin and mineral profile per 100g.")

    food_options = sorted(filtered_df["food_name"].unique().tolist())
    if not food_options:
        food_options = sorted(df_all["food_name"].unique().tolist())

    selected_food = st.selectbox("Select a Food Item to Inspect", options=food_options, index=0)

    if selected_food:
        row_match = df_all[df_all["food_name"] == selected_food].iloc[0]
        serving_info = HOUSEHOLD_SERVINGS.get(selected_food, "Standard 100g portion")
        micros = MICRONUTRIENTS_PER_100G.get(selected_food, {})

        c_info1, c_info2, c_info3, c_info4 = st.columns(4)
        with c_info1:
            st.metric("Energy (per 100g)", f"{row_match['calories']} kcal")
            st.caption(f"Category: **{row_match['food_category']}**")
        with c_info2:
            st.metric("Protein", f"{row_match['protein']} g")
            st.caption(f"Diet: **{row_match['diet_type'].upper()}**")
        with c_info3:
            st.metric("Carbohydrates", f"{row_match['carbohydrates']} g")
            st.caption(f"Fiber: **{row_match['fiber']} g**")
        with c_info4:
            st.metric("Fats", f"{row_match['fats']} g")
            st.caption(f"Allergens: **{row_match['allergens']}**")

        st.info(f"🥄 **Typical Household Serving:** {serving_info}")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown("##### Essential Minerals (per 100g)")
            min_keys = ["calcium_mg", "iron_mg", "magnesium_mg", "potassium_mg", "zinc_mg", "sodium_mg"]
            m_rows = []
            for k in min_keys:
                ref = RDA_REFERENCE.get(k, {})
                label = ref.get("label", k)
                unit = ref.get("unit", "")
                val = micros.get(k)
                val_str = f"{val:.1f} {unit}" if val is not None else "Not Reported in IFCT"
                target_str = f"{ref.get('target', 0):.0f} {unit}"
                m_rows.append({"Mineral": label, "Per 100g": val_str, "Adult RDA": target_str})
            st.dataframe(pd.DataFrame(m_rows), use_container_width=True, hide_index=True)

        with col_m2:
            st.markdown("##### Essential Vitamins (per 100g)")
            vit_keys = [
                "vitamin_a_mcg", "vitamin_b1_mg", "vitamin_b2_mg", "vitamin_b3_mg",
                "vitamin_b6_mg", "vitamin_b9_mcg", "vitamin_b12_mcg", "vitamin_c_mg",
                "vitamin_d_mcg", "vitamin_e_mg", "vitamin_k_mcg"
            ]
            v_rows = []
            for k in vit_keys:
                ref = RDA_REFERENCE.get(k, {})
                label = ref.get("label", k)
                unit = ref.get("unit", "")
                val = micros.get(k)
                val_str = f"{val:.1f} {unit}" if val is not None else "Not Reported in IFCT"
                target_str = f"{ref.get('target', 0):.1f} {unit}"
                v_rows.append({"Vitamin": label, "Per 100g": val_str, "Adult RDA": target_str})
            st.dataframe(pd.DataFrame(v_rows), use_container_width=True, hide_index=True)
