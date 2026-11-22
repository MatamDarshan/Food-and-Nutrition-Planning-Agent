"""
ui/meal_planner.py
------------------
Today and My week pages for the NutriPlan frontend.

The module keeps the original data-shaping helpers (portion cleanup, 7-day
fallback, grocery totals) intact and replaces only the presentation layer with
colour-coded cards, readable tables and focused daily/weekly dashboards.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, Callable, Optional

import pandas as pd
import streamlit as st

from config.settings import settings
from data.micronutrient_data import RDA_POPULATION, RDA_REFERENCE, RDA_SOURCE
from tools.food_tools import _get_df
from ui.components import (
    callout,
    empty_state,
    meal_card,
    metric_card,
    nutrition_table,
    progress_bar,
    render_badges,
    section_header,
    source_note,
    status_badge,
)
from ui.layout import render_page_header, render_today_hero
from ui.styles import MACRO_ACCENTS


MEAL_CONFIG = {
    "breakfast": {
        "title": "🌅 Breakfast",
        "label": "Breakfast",
        "time": "8:00 – 9:30 AM",
        "icon": "🌅",
        "desc": "Start the day with steady energy and protein.",
        "nutrition_tip": (
            "A cereal + pulse pairing gives a complete amino-acid profile with "
            "a gentle glycemic rise."
        ),
        "alternatives": [
            "Besan chilla",
            "Poha with vegetables",
            "Upma",
            "Idli + sambar",
            "Sprouts salad",
        ],
    },
    "lunch": {
        "title": "🍛 Lunch",
        "label": "Lunch",
        "time": "1:00 – 2:30 PM",
        "icon": "🍛",
        "desc": "Whole grains, dal and vegetables for sustained focus.",
        "nutrition_tip": (
            "Whole grains with lentils and curd support gut health and help "
            "prevent the mid-afternoon slump."
        ),
        "alternatives": [
            "Roti + rajma + chaas",
            "Brown rice + dal + raita",
            "Vegetable khichdi + curd",
            "Fish curry (non-veg)",
        ],
    },
    "snack": {
        "title": "🍎 Evening snack",
        "label": "Evening snack",
        "time": "4:30 – 6:00 PM",
        "icon": "🍎",
        "desc": "A light, fibre-rich bridge between lunch and dinner.",
        "nutrition_tip": (
            "Fruit, sprouts or roasted grains curb evening hunger while adding "
            "fibre and micronutrients."
        ),
        "alternatives": [
            "Moong sprouts salad",
            "Fresh apple",
            "Papaya slices",
            "Steamed dhokla",
            "Roasted makhana",
        ],
    },
    "dinner": {
        "title": "🌙 Dinner",
        "label": "Dinner",
        "time": "8:00 – 9:15 PM",
        "icon": "🌙",
        "desc": "Lean protein and fibre for overnight recovery.",
        "nutrition_tip": (
            "A lighter dinner supports muscle repair and comfortable sleep "
            "without heavy digestion."
        ),
        "alternatives": [
            "Roti + palak paneer",
            "Roti + chana masala",
            "Roti + dal makhani",
            "Egg curry (non-veg)",
            "Chicken curry (non-veg)",
        ],
    },
}

DAYS_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

SLOT_ORDER = ["breakfast", "lunch", "snack", "dinner"]


# ── Data-shaping helpers (unchanged behaviour) ───────────────────────────────

def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _day_map(days_data: Any) -> dict[str, dict]:
    if not isinstance(days_data, list):
        return {}
    return {
        str(day.get("day_name", "")).strip().title(): day
        for day in days_data
        if isinstance(day, dict)
    }


def _meal(day_info: Mapping[str, Any], slot: str) -> dict:
    return (day_info.get("meals") or {}).get(slot) or {}


def _meal_items(day_info: Mapping[str, Any], slot: str) -> list[dict]:
    items = _meal(day_info, slot).get("items") or []
    return [item for item in items if isinstance(item, dict)]


def _serving_text(item: Mapping[str, Any]) -> str:
    """Turn a verbose serving string into something a person can read."""
    raw = item.get("serving_display")
    if not raw:
        return f"{_num(item.get('quantity_g')):.0f} g"

    text = str(raw)
    text = re.sub(r"\(\s*approx\.[^)]*\)", "", text)
    text = re.sub(r"\(\s*\d+\s*[-–]\s*\d+\s*g\s*\)", "", text)
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"^\s*\d+(?:\.\d+)?\s*g\s*", "", text)
    text = re.sub(r"^\s*\(\s*", "", text).strip()
    text = text.strip("() ").strip()
    text = re.sub(r"\s{2,}", " ", text)
    return text or f"{_num(item.get('quantity_g')):.0f} g"


def _food_names(day_info: Mapping[str, Any], slot: str) -> str:
    names = [
        str(item.get("food_name", "")).strip()
        for item in _meal_items(day_info, slot)
    ]
    return ", ".join(name for name in names if name) or "—"


def _timetable_rows(day_info: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slot in SLOT_ORDER:
        config = MEAL_CONFIG[slot]
        rows.append(
            {
                "Time": config["time"],
                "Meal": config["label"],
                "Foods": _food_names(day_info, slot),
                "Calories (kcal)": int(
                    round(_num(_meal(day_info, slot).get("total_calories")))
                ),
            }
        )
    return rows


def _timetable(day_info: Mapping[str, Any]) -> None:
    nutrition_table(
        pd.DataFrame(_timetable_rows(day_info)),
        alt="Today's meal timetable with times, meal names, foods and calories",
        column_config={
            "Time": st.column_config.TextColumn("Time", width="small"),
            "Meal": st.column_config.TextColumn("Meal", width="small"),
            "Foods": st.column_config.TextColumn("Foods", width="large"),
            "Calories (kcal)": st.column_config.NumberColumn(
                "Calories (kcal)", format="%d", width="small"
            ),
        },
    )


def _fallback_weekly_plan(
    meal_plan: Optional[dict],
    targets: Optional[dict],
) -> Optional[dict]:
    """Build a displayable 7-day plan if the engine only returned one day."""
    if not isinstance(meal_plan, dict) or not meal_plan:
        return None
    try:
        from core.calculations import build_day_plan_detail, calculate_weekly_averages
        from core.schemas import NutritionTargets, WeeklyPlan

        targets_obj = (
            NutritionTargets(**targets)
            if targets
            else NutritionTargets(
                bmi=0.0,
                bmi_category="Unknown",
                bmr=0.0,
                tdee=0.0,
                calorie_target=2000.0,
                protein_g=90.0,
                carbs_g=240.0,
                fats_g=55.0,
                fiber_g=28.0,
            )
        )
        food_df = _get_df()
        days = [
            build_day_plan_detail(
                day_name,
                meal_plan,
                food_df,
                target_calories=targets_obj.calorie_target,
            )
            for day_name in DAYS_ORDER
        ]
        averages = calculate_weekly_averages(days, targets_obj)
        plan = WeeklyPlan(
            user_targets=targets_obj,
            days=days,
            weekly_averages=averages,
            rationale=(
                "A single-day plan was returned by the engine. It is shown across "
                "all seven days so you can review the timetable and nutrition."
            ),
            source_references=[
                "ICMR-NIN Indian Food Composition Tables (IFCT 2017)",
                "ICMR-NIN Dietary Guidelines for Indians & RDA 2020",
            ],
        )
        return plan.model_dump()
    except Exception:
        return None


def _resolve_plan(
    weekly_plan: Optional[dict],
    meal_plan: Optional[dict],
    targets: Optional[dict],
) -> Optional[dict]:
    plan = weekly_plan
    if not isinstance(plan, dict) or not plan.get("days"):
        plan = _fallback_weekly_plan(meal_plan, targets)
    if not isinstance(plan, dict) or not plan.get("days"):
        return None
    return plan


# ── Shared visual helpers ─────────────────────────────────────────────────────

def _profile_badges(profile: Optional[dict], targets: Optional[dict]) -> list[dict[str, str]]:
    profile = profile or {}
    targets = targets or {}
    diet = "🌱 Vegetarian" if profile.get("diet_type", "veg") == "veg" else "🍗 Non-vegetarian"
    goal = str(profile.get("fitness_goal", "maintenance")).replace("_", " ").title()
    calories = _num(targets.get("calorie_target"))
    allergies = profile.get("allergies") or []

    badges = [
        {"label": diet, "tone": "green", "icon": "🥗"},
        {"label": f"Goal: {goal}", "tone": "blue", "icon": "🎯"},
        {
            "label": "Allergy: " + ", ".join(str(a) for a in allergies)
            if allergies
            else "No allergies set",
            "tone": "red" if allergies else "teal",
            "icon": "⚠️" if allergies else "✅",
        },
    ]
    if calories:
        badges.append(
            {"label": f"{calories:,.0f} kcal target", "tone": "orange", "icon": "🔥"}
        )
    badges.append(
        {
            "label": "Gemini Live" if settings.api_key else "Offline Fallback",
            "tone": "green" if settings.api_key else "blue",
            "icon": "🟢" if settings.api_key else "💡",
        }
    )
    return badges


def _validation_line(validation: Any) -> None:
    if not validation:
        return
    if isinstance(validation, Mapping):
        is_valid = bool(validation.get("is_valid", True))
        issues = validation.get("issues") or []
    else:
        is_valid = bool(getattr(validation, "is_valid", True))
        issues = getattr(validation, "issues", []) or []

    if is_valid:
        render_badges(
            [{"label": "All 7 days checked", "tone": "green", "icon": "✅"}]
        )
    else:
        st.warning(
            "Some days need a closer look: " + "; ".join(str(i) for i in issues[:3])
        )


def _metric_grid(day_info: Mapping[str, Any], targets: Mapping[str, Any]) -> None:
    t_cal = _num(targets.get("calorie_target"), 2000.0)
    t_prot = _num(targets.get("protein_g"), 1.0)
    t_carb = _num(targets.get("carbs_g"), 1.0)
    t_fat = _num(targets.get("fats_g"), 1.0)
    t_fibre = _num(targets.get("fiber_g"), 1.0)

    d_cal = _num(day_info.get("total_calories"))
    d_prot = _num(day_info.get("total_protein"))
    d_carb = _num(day_info.get("total_carbs"))
    d_fat = _num(day_info.get("total_fat"))
    d_fibre = _num(day_info.get("total_fiber"))

    specs = [
        ("Calories (kcal)", f"{d_cal:,.0f}", t_cal, "calories", "Planned energy"),
        ("Protein (g)", f"{d_prot:.0f}", t_prot, "protein", "Muscle & satiety"),
        ("Carbs (g)", f"{d_carb:.0f}", t_carb, "carbs", "Steady energy"),
        ("Fats (g)", f"{d_fat:.0f}", t_fat, "fats", "Hormones & absorption"),
    ]
    columns = st.columns(4)
    for column, (label, value, target, tone, hint) in zip(columns, specs):
        with column:
            ratio = 0.0 if target <= 0 else d_cal / target if tone == "calories" else 0.0
            metric_card(
                label=label,
                value=value,
                target=target,
                ratio=ratio if tone == "calories" else None,
                tone=tone,
                caption=hint,
            )

    fibre_pct = 0.0 if t_fibre <= 0 else min(d_fibre / t_fibre, 1.0) * 100
    st.markdown(
        f"<div class='np-callout' style='--np-accent:{MACRO_ACCENTS['fibre']};"
        f"--np-callout-bg:#E5F6F3;'>🥬 <strong>Fibre</strong> "
        f"{d_fibre:.0f} g of {t_fibre:.0f} g target "
        f"({fibre_pct:.0f}%)</div>",
        unsafe_allow_html=True,
    )


def _day_summary(
    day_info: Mapping[str, Any],
    targets: Mapping[str, Any],
    show_timetable: bool = True,
) -> None:
    _metric_grid(day_info, targets)

    if show_timetable:
        section_header(
            "Today's Meal Timetable",
            subtitle="A quick look at meal times, foods and calories.",
            icon="🕒",
            level=5,
        )
        _timetable(day_info)

    section_header("Your meals", subtitle="Food-level detail for every slot.", icon="🍽️", level=5)
    for slot in SLOT_ORDER:
        meal_card(day_info, slot, MEAL_CONFIG[slot], _serving_text)


def _nutrition_details(day_info: Mapping[str, Any]) -> None:
    with st.expander("📋 Full food-by-food nutrition"):
        rows = []
        for slot in SLOT_ORDER:
            for item in _meal_items(day_info, slot):
                rows.append(
                    {
                        "Meal": MEAL_CONFIG[slot]["label"],
                        "Food": item.get("food_name", ""),
                        "Portion": _serving_text(item),
                        "kcal": int(round(_num(item.get("calories")))),
                        "Protein (g)": round(_num(item.get("protein")), 1),
                        "Carbs (g)": round(_num(item.get("carbohydrates")), 1),
                        "Fat (g)": round(_num(item.get("fat")), 1),
                        "Fibre (g)": round(_num(item.get("fiber")), 1),
                    }
                )
        nutrition_table(
            pd.DataFrame(rows),
            alt="Food-by-food nutrition for the selected day",
            column_config={
                "Meal": st.column_config.TextColumn("Meal", width="small"),
                "Food": st.column_config.TextColumn("Food", width="large"),
                "Portion": st.column_config.TextColumn("Portion", width="medium"),
                "kcal": st.column_config.NumberColumn("kcal", format="%d", width="small"),
            },
        )


def _micronutrients(day_info: Mapping[str, Any]) -> None:
    with st.expander("🔬 Vitamins & minerals"):
        _micronutrients_body(day_info)


def _daily_insights(
    day_info: Mapping[str, Any],
    targets: Mapping[str, Any],
    validation: Any,
) -> None:
    with st.expander("💡 Daily nutrition insights"):
        t_cal = _num(targets.get("calorie_target"), 2000.0)
        d_cal = _num(day_info.get("total_calories"))
        if t_cal > 0:
            progress_bar("Energy used", d_cal, t_cal, tone="calories")
        for label, key, target_key, tone in [
            ("Protein", "total_protein", "protein_g", "protein"),
            ("Carbohydrates", "total_carbs", "carbs_g", "carbs"),
            ("Fats", "total_fat", "fats_g", "fats"),
            ("Fibre", "total_fiber", "fiber_g", "fibre"),
        ]:
            target_value = _num(targets.get(target_key), 1.0)
            if target_value > 0:
                progress_bar(
                    label,
                    _num(day_info.get(key)),
                    target_value,
                    tone=tone,
                )

        if isinstance(validation, Mapping) and validation.get("issues"):
            callout("; ".join(str(x) for x in validation["issues"][:3]), tone="amber")
        elif isinstance(validation, Mapping) and validation.get("is_valid"):
            callout("This day passes the allergy, diet, exclusion and calorie checks.", tone="green")
        else:
            callout("Targets are estimates for planning, not clinical advice.", tone="blue")

        st.caption(
            MEAL_CONFIG["breakfast"]["nutrition_tip"]
            + " "
            + MEAL_CONFIG["dinner"]["nutrition_tip"]
        )


def _plan_actions(on_generate: Optional[Callable[[], None]], key_suffix: str) -> None:
    with st.expander("⚙️ Plan actions"):
        st.caption("Rebuild a fresh 7-day plan using your current profile and targets.")
        if on_generate:
            st.button(
                "🔄 Rebuild plan" if key_suffix == "today" else "🔄 Rebuild weekly plan",
                width="stretch",
                key=f"{key_suffix}_rebuild_plan",
                on_click=on_generate,
            )
        else:
            st.info("Plan rebuilding is unavailable in this view.")


# ── Today page ────────────────────────────────────────────────────────────────

def render_today_page(
    weekly_plan: Optional[dict[str, Any]],
    targets: Optional[dict[str, Any]],
    validation_result: Optional[dict[str, Any]] = None,
    user_name: str = "User",
    meal_plan: Optional[dict[str, Any]] = None,
    on_generate: Optional[Callable[[], None]] = None,
    on_new_profile: Optional[Callable[[], None]] = None,
    user_profile: Optional[dict[str, Any]] = None,
) -> None:
    """Render the default single-day meal dashboard."""
    targets = targets or {}
    render_today_hero(user_name, _profile_badges(user_profile, targets))

    if not targets:
        empty_state(
            "Let's build your first plan",
            "Add a few details about yourself and NutriPlan will calculate your "
            "targets and design seven days of Indian meals.",
            icon="👤",
            action_label="＋ Create my profile",
            on_action=on_new_profile,
            key="today_new_profile",
        )
        return

    plan = _resolve_plan(weekly_plan, meal_plan, targets)
    if not plan:
        empty_state(
            "Your plan is not ready yet",
            "Build a meal plan to see your daily calories, meal times and food list.",
            icon="🍱",
            action_label="⚡ Build my meal plan",
            on_action=on_generate,
            key="planner_generate_btn",
        )
        return

    day_map = _day_map(plan.get("days"))
    today_name = datetime.now().strftime("%A")
    focus_day = today_name if today_name in day_map else DAYS_ORDER[0]
    day_info = day_map.get(focus_day) or {}

    section_header(
        f"Today, {focus_day}",
        subtitle=datetime.now().strftime("%d %b") + " · your plan at a glance",
        icon="🍽️",
        level=3,
    )
    _validation_line(plan.get("validation_result") or validation_result)
    st.write("")

    _day_summary(day_info, targets, show_timetable=True)
    st.write("")
    _nutrition_details(day_info)
    _micronutrients(day_info)
    _daily_insights(day_info, targets, plan.get("validation_result") or validation_result)
    _plan_actions(on_generate, "today")


# ── Week page ─────────────────────────────────────────────────────────────────

def _week_frame(day_map: Mapping[str, dict]) -> pd.DataFrame:
    rows = []
    for day_name in DAYS_ORDER:
        info = day_map.get(day_name) or {}
        rows.append(
            {
                "Day": day_name,
                "Calories (kcal)": int(round(_num(info.get("total_calories")))),
                "Protein (g)": round(_num(info.get("total_protein")), 0),
                "Carbs (g)": round(_num(info.get("total_carbs")), 0),
                "Fats (g)": round(_num(info.get("total_fat")), 0),
                "Fibre (g)": round(_num(info.get("total_fiber")), 0),
            }
        )
    return pd.DataFrame(rows)


def _weekly_average_cards(avg: Mapping[str, Any]) -> None:
    devs = avg.get("macro_deviations") or {}
    specs = [
        ("Avg Calories", _num(avg.get("avg_calories")), "kcal", "calories", _num(devs.get("calories_pct"))),
        ("Avg Protein", _num(avg.get("avg_protein")), "g", "protein", _num(devs.get("protein_pct"))),
        ("Avg Carbs", _num(avg.get("avg_carbs")), "g", "carbs", _num(devs.get("carbs_pct"))),
        ("Avg Fat", _num(avg.get("avg_fat")), "g", "fats", _num(devs.get("fat_pct"))),
    ]
    columns = st.columns(4)
    for column, (label, value, unit, tone, deviation) in zip(columns, specs):
        with column:
            metric_card(
                label=label,
                value=f"{value:,.0f} {unit}" if unit == "kcal" else f"{value:.0f} {unit}",
                tone=tone,
                delta=f"{deviation:+.1f}% vs target",
            )
    st.markdown(
        '<div class="np-badges">'
        + "".join(
            status_badge(_num(devs.get(key)))
            for key in ["calories_pct", "protein_pct", "carbs_pct", "fat_pct"]
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def _grocery_rows(day_map: Mapping[str, dict]) -> list[dict[str, Any]]:
    totals: dict[str, dict[str, Any]] = {}
    for day_name in DAYS_ORDER:
        info = day_map.get(day_name) or {}
        for slot in SLOT_ORDER:
            for item in _meal_items(info, slot):
                name = str(item.get("food_name", "")).strip()
                if not name:
                    continue
                entry = totals.setdefault(
                    name, {"quantity": 0.0, "days": set(), "category": "Other"}
                )
                entry["quantity"] += _num(item.get("quantity_g"))
                entry["days"].add(day_name)

    category_map: dict[str, str] = {}
    try:
        frame = _get_df()
        category_map = {
            str(name).strip().lower(): str(category)
            for name, category in zip(frame["food_name"], frame["food_category"])
        }
    except Exception:
        category_map = {}

    rows: list[dict[str, Any]] = []
    for name, entry in totals.items():
        quantity = float(entry["quantity"])
        rows.append(
            {
                "Category": category_map.get(name.strip().lower(), "Other"),
                "Food": name,
                "Weekly quantity": (
                    f"{quantity / 1000:.2f} kg"
                    if quantity >= 1000
                    else f"{quantity:.0f} g"
                ),
                "Days used": len(entry["days"]),
            }
        )
    return sorted(rows, key=lambda row: (row["Category"], row["Food"]))


def _printable_menu(day_map: Mapping[str, dict]) -> str:
    lines: list[str] = []
    for day_name in DAYS_ORDER:
        info = day_map.get(day_name) or {}
        lines.append(f"{day_name.upper()} — {_num(info.get('total_calories')):.0f} kcal")
        for slot in SLOT_ORDER:
            lines.append(
                f"  {MEAL_CONFIG[slot]['time']} · {MEAL_CONFIG[slot]['label']}: "
                f"{_food_names(info, slot)}"
            )
        lines.append("")
    return "\n".join(lines)


def render_week_page(
    weekly_plan: Optional[dict[str, Any]],
    targets: Optional[dict[str, Any]],
    validation_result: Optional[dict[str, Any]] = None,
    user_name: str = "User",
    meal_plan: Optional[dict[str, Any]] = None,
    on_generate: Optional[Callable[[], None]] = None,
    user_profile: Optional[dict[str, Any]] = None,
    on_new_profile: Optional[Callable[[], None]] = None,
) -> None:
    """Render the weekly overview, selected day and planning utilities."""
    targets = targets or {}
    render_page_header(
        "My week",
        subtitle="Seven days of meals, nutrition totals and a ready-to-use grocery list.",
        icon="📅",
        badges=_profile_badges(user_profile, targets),
    )

    if not targets:
        empty_state(
            "No weekly targets yet",
            "Create a profile to calculate your targets and generate a full week.",
            icon="👤",
            action_label="＋ Create my profile",
            on_action=on_new_profile,
            key="week_new_profile",
        )
        return

    plan = _resolve_plan(weekly_plan, meal_plan, targets)
    if not plan:
        empty_state(
            "Your weekly plan is not ready yet",
            "Build a plan to compare all seven days against your daily targets.",
            icon="📅",
            action_label="⚡ Build my meal plan",
            on_action=on_generate,
            key="week_generate_btn",
        )
        return

    day_map = _day_map(plan.get("days"))
    _validation_line(plan.get("validation_result") or validation_result)

    section_header("7-day nutrition", icon="📊", level=4)
    nutrition_table(
        _week_frame(day_map),
        alt="Seven-day nutrition table with calories and macronutrients",
        column_config={
            "Day": st.column_config.TextColumn("Day", width="small"),
            "Calories (kcal)": st.column_config.NumberColumn("Calories (kcal)", format="%d", width="small"),
            "Protein (g)": st.column_config.NumberColumn("Protein (g)", format="%d", width="small"),
            "Carbs (g)": st.column_config.NumberColumn("Carbs (g)", format="%d", width="small"),
            "Fats (g)": st.column_config.NumberColumn("Fats (g)", format="%d", width="small"),
            "Fibre (g)": st.column_config.NumberColumn("Fibre (g)", format="%d", width="small"),
        },
    )

    avg = plan.get("weekly_averages") or {}
    if avg:
        section_header("Weekly averages vs targets", icon="📈", level=4)
        _weekly_average_cards(avg)
        limitation_note = avg.get("limitation_note")
        if limitation_note:
            callout(str(limitation_note), tone="blue", icon="💡")

    with st.expander("📈 Calories across the week"):
        weekly = pd.DataFrame(
            {
                "Day": DAYS_ORDER,
                "Planned": [
                    _num((day_map.get(day) or {}).get("total_calories"))
                    for day in DAYS_ORDER
                ],
                "Target": [_num(targets.get("calorie_target"), 2000.0)] * len(DAYS_ORDER),
            }
        ).set_index("Day")
        st.bar_chart(
            weekly,
            alt="Daily planned calories compared with the daily calorie target",
        )

    st.write("")
    today_name = datetime.now().strftime("%A")
    chosen_day = st.selectbox(
        "Show a day",
        options=DAYS_ORDER,
        index=DAYS_ORDER.index(today_name) if today_name in DAYS_ORDER else 0,
    )
    day_info = day_map.get(chosen_day) or {}
    section_header(chosen_day, subtitle="Full meal detail for the selected day.", icon="🍽️", level=3)
    _day_summary(day_info, targets, show_timetable=True)

    st.write("")
    with st.expander("🛒 Grocery list for the week"):
        rows = _grocery_rows(day_map)
        if rows:
            nutrition_table(
                pd.DataFrame(rows),
                alt="Weekly grocery totals grouped by food category",
                column_config={
                    "Category": st.column_config.TextColumn("Category", width="small"),
                    "Food": st.column_config.TextColumn("Food", width="large"),
                    "Weekly quantity": st.column_config.TextColumn("Weekly quantity", width="small"),
                    "Days used": st.column_config.NumberColumn("Days used", format="%d", width="small"),
                },
            )
            grocery_text = "\n".join(
                f"{row['Category']} · {row['Food']}: {row['Weekly quantity']}"
                for row in rows
            )
            st.text_area(
                "Copy grocery list",
                value=grocery_text,
                height=160,
                key="grocery_copy_list",
                label_visibility="collapsed",
            )
        else:
            st.caption("Nothing to total yet.")

    with st.expander("🖨️ Printable weekly menu"):
        st.text_area(
            "Copy or print",
            value=_printable_menu(day_map),
            height=220,
            key="planner_printable_menu",
            label_visibility="collapsed",
        )

    with st.expander("🔬 Vitamins & minerals"):
        _micronutrients_body(day_info)

    _plan_actions(on_generate, "week")


def _micronutrients_body(day_info: Mapping[str, Any]) -> None:
    """Render vitamin and mineral tables for a selected day."""
    micros = day_info.get("micronutrients") or {}
    groups = {
        "Minerals": ["calcium_mg", "iron_mg", "magnesium_mg", "potassium_mg", "zinc_mg"],
        "Vitamins": [
            "vitamin_a_mcg",
            "vitamin_b2_mg",
            "vitamin_b9_mcg",
            "vitamin_b12_mcg",
            "vitamin_c_mg",
            "vitamin_d_mcg",
        ],
    }

    def frame(keys: list[str], label: str) -> pd.DataFrame:
        rows = []
        for key in keys:
            reference = RDA_REFERENCE.get(key, {})
            unit = reference.get("unit", "")
            target = _num(reference.get("target"))
            value = micros.get(key)
            pct = (value / target * 100) if (value is not None and target > 0) else None
            rows.append(
                {
                    label: reference.get("label", key),
                    "Today": f"{_num(value):.1f} {unit}" if value is not None else "Not Reported in IFCT",
                    "RDA 2020": f"{target:.0f} {unit}",
                    "% RDA": f"{pct:.0f}%" if pct is not None else "—",
                }
            )
        return pd.DataFrame(rows)

    source_note(f"Reference population: {RDA_POPULATION} · Source: {RDA_SOURCE}")
    left, right = st.columns(2)
    with left:
        st.markdown("**Minerals**")
        nutrition_table(
            frame(groups["Minerals"], "Mineral"),
            alt="Mineral intake compared with adult RDA",
        )
    with right:
        st.markdown("**Vitamins**")
        nutrition_table(
            frame(groups["Vitamins"], "Vitamin"),
            alt="Vitamin intake compared with adult RDA",
        )


def render_7day_meal_planner(
    weekly_plan: Optional[dict[str, Any]],
    targets: Optional[dict[str, Any]],
    validation_result: Optional[dict[str, Any]] = None,
    user_name: str = "User",
    meal_plan: Optional[dict[str, Any]] = None,
    on_generate: Optional[Callable[[], None]] = None,
    user_profile: Optional[dict[str, Any]] = None,
) -> None:
    """Backwards-compatible entry point used by older callers."""
    render_today_page(
        weekly_plan=weekly_plan,
        targets=targets,
        validation_result=validation_result,
        user_name=user_name,
        meal_plan=meal_plan,
        on_generate=on_generate,
        user_profile=user_profile,
    )


__all__ = [
    "DAYS_ORDER",
    "MEAL_CONFIG",
    "SLOT_ORDER",
    "render_7day_meal_planner",
    "render_today_page",
    "render_week_page",
]
