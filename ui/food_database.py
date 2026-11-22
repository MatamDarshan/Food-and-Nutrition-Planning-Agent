"""
ui/food_database.py
-------------------
Colourful Indian Food Database Explorer.

The page reads the unchanged ICMR-NIN IFCT 2017 food table and micronutrient
dictionary, then presents them with search, filters, a result counter, a wide
nutrition table and a detailed food inspector.  Missing micronutrient values stay
explicitly labelled "Not Reported in IFCT" — they are never invented or filled
with zero.
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import streamlit as st

from data.micronutrient_data import (
    HOUSEHOLD_SERVINGS,
    MICRONUTRIENTS_PER_100G,
    RDA_REFERENCE,
)
from tools.food_tools import _get_df
from ui.components import (
    callout,
    nutrition_table,
    progress_bar,
    render_badges,
    section_header,
    source_note,
    stat_tile,
)
from ui.layout import render_page_header


NOT_REPORTED = "Not Reported in IFCT"

MINERAL_KEYS = [
    "calcium_mg",
    "iron_mg",
    "magnesium_mg",
    "potassium_mg",
    "zinc_mg",
    "sodium_mg",
]

VITAMIN_KEYS = [
    "vitamin_a_mcg",
    "vitamin_b1_mg",
    "vitamin_b2_mg",
    "vitamin_b3_mg",
    "vitamin_b6_mg",
    "vitamin_b9_mcg",
    "vitamin_b12_mcg",
    "vitamin_c_mg",
    "vitamin_d_mcg",
    "vitamin_e_mg",
    "vitamin_k_mcg",
]


def _display_value(value: Any, decimals: int = 1) -> str:
    """Format a numeric cell without turning missing data into zero."""
    if value is None or pd.isna(value):
        return "—"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def _micro_frame(keys: list[str], micros: dict[str, Optional[float]], label: str) -> pd.DataFrame:
    """Build a per-100 g micronutrient table with RDA comparison."""
    rows: list[dict[str, str]] = []
    for key in keys:
        reference = RDA_REFERENCE.get(key, {})
        unit = str(reference.get("unit", ""))
        target = float(reference.get("target", 0) or 0)
        value = micros.get(key)
        value_text = f"{float(value):.1f} {unit}" if value is not None else NOT_REPORTED
        target_text = f"{target:.1f} {unit}" if target % 1 else f"{target:.0f} {unit}"
        pct_text = (
            f"{float(value) / target * 100:.0f}%"
            if value is not None and target > 0
            else "—"
        )
        rows.append(
            {
                label: str(reference.get("label", key)),
                "Per 100 g": value_text,
                "Adult RDA": target_text,
                "% RDA": pct_text,
            }
        )
    return pd.DataFrame(rows)


def _render_micro_bars(micros: dict[str, Optional[float]], keys: list[str]) -> None:
    """Add visual RDA context without inventing absent values."""
    for key in keys:
        reference = RDA_REFERENCE.get(key, {})
        value = micros.get(key)
        if value is None:
            continue
        target = float(reference.get("target", 0) or 0)
        if target <= 0:
            continue
        progress_bar(
            label=str(reference.get("label", key)),
            current=float(value),
            target=target,
            tone="teal",
            note=f"Per 100 g · adult RDA {target:.0f} {reference.get('unit', '')}",
        )


def render_food_database_page() -> None:
    """Render the searchable ICMR-NIN food composition explorer."""
    render_page_header(
        "Indian Food Composition Database",
        subtitle="Authentic per-100 g nutrition from the ICMR-National Institute of Nutrition, IFCT 2017.",
        icon="🔍",
        badges=[
            {"label": "IFCT 2017", "tone": "green", "icon": "📚"},
            {"label": "Vitamins & minerals", "tone": "purple", "icon": "🔬"},
            {"label": "Household servings", "tone": "orange", "icon": "🥄"},
        ],
    )

    df_all = _get_df()

    filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])
    with filter_col1:
        search_query = st.text_input(
            "Search food by name",
            placeholder="Try Idli, Paneer, Dal or Chicken...",
        )
    with filter_col2:
        diet_filter = st.selectbox(
            "Dietary Category",
            options=["All", "Vegetarian", "Non-Vegetarian"],
            index=0,
        )
    with filter_col3:
        all_categories = sorted(str(x) for x in df_all["food_category"].unique().tolist())
        cat_filter = st.selectbox(
            "Food Group / Category",
            options=["All"] + all_categories,
            index=0,
        )

    filtered_df = df_all.copy()
    if search_query:
        filtered_df = filtered_df[
            filtered_df["food_name"].str.contains(search_query, case=False, na=False)
        ]
    if diet_filter == "Vegetarian":
        filtered_df = filtered_df[filtered_df["diet_type"] == "veg"]
    elif diet_filter == "Non-Vegetarian":
        filtered_df = filtered_df[filtered_df["diet_type"] == "non-veg"]
    if cat_filter != "All":
        filtered_df = filtered_df[filtered_df["food_category"] == cat_filter]

    render_badges(
        [
            {"label": f"Showing {len(filtered_df)} of {len(df_all)} foods", "tone": "green", "icon": "🔎"},
            {"label": "Values per 100 g", "tone": "blue", "icon": "⚖️"},
        ]
    )

    display_cols = [
        "food_name",
        "food_category",
        "diet_type",
        "calories",
        "protein",
        "carbohydrates",
        "fats",
        "fiber",
        "glycemic_index",
        "allergens",
    ]
    renamed_cols = {
        "food_name": "Food Name",
        "food_category": "Category",
        "diet_type": "Diet Type",
        "calories": "Calories (kcal)",
        "protein": "Protein (g)",
        "carbohydrates": "Carbs (g)",
        "fats": "Fats (g)",
        "fiber": "Fibre (g)",
        "glycemic_index": "Glycaemic Index",
        "allergens": "Allergen Tags",
    }
    view_df = filtered_df[display_cols].rename(columns=renamed_cols)
    for numeric_col in ["Calories (kcal)", "Protein (g)", "Carbs (g)", "Fats (g)", "Fibre (g)"]:
        view_df[numeric_col] = view_df[numeric_col].map(lambda v: _display_value(v, 1))
    view_df["Glycaemic Index"] = view_df["Glycaemic Index"].map(lambda v: _display_value(v, 0))
    view_df["Allergen Tags"] = view_df["Allergen Tags"].fillna("None").replace("", "None")

    section_header(
        "Food results",
        subtitle="Scroll or sort the table, then choose a food below to inspect it.",
        icon="🍽️",
        level=4,
    )
    nutrition_table(
        view_df,
        alt="Searchable Indian food composition results",
        column_config={
            "Food Name": st.column_config.TextColumn("Food Name", width="large"),
            "Category": st.column_config.TextColumn("Category", width="medium"),
            "Diet Type": st.column_config.TextColumn("Diet Type", width="small"),
            "Allergen Tags": st.column_config.TextColumn("Allergen Tags", width="medium"),
        },
    )

    section_header(
        "Food inspector",
        subtitle="Portion, macronutrients, vitamins, minerals and adult RDA context.",
        icon="🔬",
        level=4,
    )
    food_options = sorted(str(x) for x in filtered_df["food_name"].unique().tolist())
    if not food_options:
        food_options = sorted(str(x) for x in df_all["food_name"].unique().tolist())

    selected_food = st.selectbox(
        "Select a Food Item to Inspect",
        options=food_options,
        index=0,
    )
    if not selected_food:
        callout("Choose a food from the results above to inspect it.", tone="blue")
        return

    row_match = df_all[df_all["food_name"] == selected_food].iloc[0]
    serving_info = HOUSEHOLD_SERVINGS.get(selected_food, "Standard 100 g portion")
    micros = MICRONUTRIENTS_PER_100G.get(selected_food, {})

    metric_cols = st.columns(4)
    with metric_cols[0]:
        stat_tile(
            "Energy",
            f"{_display_value(row_match['calories'], 0)} kcal",
            tone="orange",
            hint=str(row_match["food_category"]),
        )
    with metric_cols[1]:
        stat_tile(
            "Protein",
            f"{_display_value(row_match['protein'], 1)} g",
            tone="green",
            hint=f"Diet: {str(row_match['diet_type']).upper()}",
        )
    with metric_cols[2]:
        stat_tile(
            "Carbohydrates",
            f"{_display_value(row_match['carbohydrates'], 1)} g",
            tone="blue",
            hint=f"Fibre: {_display_value(row_match['fiber'], 1)} g",
        )
    with metric_cols[3]:
        stat_tile(
            "Fats",
            f"{_display_value(row_match['fats'], 1)} g",
            tone="purple",
            hint=f"Allergens: {row_match['allergens'] or 'None'}",
        )

    callout(f"Typical household serving: {serving_info}", tone="orange", icon="🥄")

    micro_col1, micro_col2 = st.columns(2)
    with micro_col1:
        st.markdown("**Essential minerals (per 100 g)**")
        nutrition_table(
            _micro_frame(MINERAL_KEYS, micros, "Mineral"),
            alt="Mineral composition of the selected food per 100 g",
        )
    with micro_col2:
        st.markdown("**Essential vitamins (per 100 g)**")
        nutrition_table(
            _micro_frame(VITAMIN_KEYS, micros, "Vitamin"),
            alt="Vitamin composition of the selected food per 100 g",
        )

    with st.expander("📊 RDA context bars"):
        st.caption(
            "A single food is not expected to meet a full day's requirement. "
            "Bars show how much of the adult RDA is present in 100 g of this food."
        )
        left, right = st.columns(2)
        with left:
            _render_micro_bars(micros, MINERAL_KEYS)
        with right:
            _render_micro_bars(micros, VITAMIN_KEYS)

    source_note(
        "Source: ICMR-National Institute of Nutrition, Indian Food Composition "
        "Tables (IFCT 2017) and ICMR-NIN RDA 2020. Missing values remain "
        "'Not Reported in IFCT'."
    )


__all__ = ["render_food_database_page"]
