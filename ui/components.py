"""
ui/components.py
----------------
Reusable visual building blocks for the NutriPlan frontend.

Every helper is presentation-only.  No nutrition, validation, retrieval or
agent logic lives here; callers pass already-calculated values and the helper
decides how to display them clearly.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from html import escape
from typing import Any, Optional

import pandas as pd
import streamlit as st

from ui.styles import (
    ACCENTS,
    ACCENT_BACKGROUNDS,
    GREEN,
    MEAL_ACCENTS,
    RED,
)


# ── Low-level HTML helpers ────────────────────────────────────────────────────

def _html(markup: str) -> None:
    """Render trusted, locally-built markup."""
    st.markdown(markup, unsafe_allow_html=True)


def _tone(tone: str) -> str:
    """Return a safe CSS tone name."""
    return tone if tone in ACCENTS else "green"


# ── Section headers and badges ────────────────────────────────────────────────

def section_header(
    title: str,
    subtitle: Optional[str] = None,
    icon: Optional[str] = None,
    level: int = 4,
    kicker: Optional[str] = None,
) -> None:
    """Render a consistent section heading with an optional kicker and hint."""
    if kicker:
        _html(f'<div class="np-section-kicker">{escape(kicker)}</div>')
    prefix = f"{icon} " if icon else ""
    hashes = "#" * max(2, min(6, level))
    st.markdown(f"{hashes} {prefix}{escape(title)}")
    if subtitle:
        st.caption(subtitle)


def badge(text: str, tone: str = "green", icon: Optional[str] = None) -> str:
    """Return a pill-shaped badge as an HTML string."""
    safe_text = escape(str(text))
    safe_icon = f"{escape(icon)} " if icon else ""
    return (
        f'<span class="np-badge np-badge--{_tone(tone)}">'
        f"{safe_icon}{safe_text}</span>"
    )


def render_badges(items: Iterable[Mapping[str, str]]) -> None:
    """Render a wrapping row of badges.

    Each mapping should contain ``label`` and may contain ``tone`` and ``icon``.
    """
    badges = []
    for item in items:
        if not item.get("label"):
            continue
        badges.append(
            badge(
                str(item["label"]),
                tone=str(item.get("tone", "green")),
                icon=item.get("icon"),
            )
        )
    if badges:
        _html('<div class="np-badges">' + "".join(badges) + "</div>")


def status_badge(pct: float) -> str:
    """Return a deviation badge whose text states the status, not just colour."""
    magnitude = abs(float(pct))
    if magnitude <= 10:
        tone, label = "green", "Close to target"
    elif magnitude <= 20:
        tone, label = "amber", "Moderate deviation"
    else:
        tone, label = "red", "Large deviation"
    return badge(f"{label} ({pct:+.1f}%)", tone=tone, icon="●")


# ── Metric cards and progress ─────────────────────────────────────────────────

def metric_card(
    label: str,
    value: str,
    target: Optional[float] = None,
    ratio: Optional[float] = None,
    tone: str = "green",
    caption: Optional[str] = None,
    delta: Optional[str] = None,
) -> None:
    """Render a coloured accent, a native metric and an optional progress bar.

    Native ``st.metric`` is intentionally used so screen readers and the AppTest
    suite can identify values, while the surrounding CSS supplies the visual
    card treatment.  ``value`` should already be formatted by the caller so it
    remains short enough to read without truncation.
    """
    color = ACCENTS.get(_tone(tone), GREEN)
    _html(
        f'<div class="np-metric-accent" style="--np-accent:{color};"></div>'
    )
    st.metric(label, str(value), delta=delta, border=True)
    if target is not None:
        progress_bar(
            label=f"Target {target:,.0f}",
            current=float(str(value).replace(",", "").split()[0])
            if _numeric_prefix(value)
            else 0.0,
            target=float(target),
            tone=tone,
            note=caption,
        )
    elif caption:
        st.caption(caption)
    if ratio is not None and target is None:
        st.caption(f"{ratio * 100:.0f}% of target")


def _numeric_prefix(value: str) -> bool:
    """Return whether a formatted metric value starts with a number."""
    try:
        float(str(value).replace(",", "").split()[0])
        return True
    except (ValueError, IndexError):
        return False


def progress_bar(
    label: str,
    current: float,
    target: float,
    tone: str = "green",
    note: Optional[str] = None,
    show_pct: bool = True,
) -> None:
    """Render an accessible custom progress bar with a written percentage."""
    color = ACCENTS.get(_tone(tone), GREEN)
    target_value = float(target) if target else 0.0
    ratio = 0.0 if target_value <= 0 else max(0.0, min(current / target_value, 1.0))
    pct = ratio * 100
    note_html = (
        f'<div class="np-progress-note">{escape(note)}</div>' if note else ""
    )
    pct_html = (
        f"<strong>{pct:.0f}%</strong>" if show_pct else "<strong>Done</strong>"
    )
    _html(
        f'<div class="np-progress-wrap">'
        f'<div class="np-progress-meta"><span>{escape(label)}</span>{pct_html}</div>'
        f'<div class="np-progress-track" role="progressbar" '
        f'aria-valuenow="{pct:.0f}" aria-valuemin="0" aria-valuemax="100">'
        f'<div class="np-progress-fill" style="width:{pct:.1f}%;background:{color};"></div>'
        f"</div>{note_html}</div>"
    )


def stat_tile(label: str, value: str, tone: str = "green", hint: Optional[str] = None) -> None:
    """Render a compact KPI tile used by dashboard and inspector panels."""
    color = ACCENTS.get(_tone(tone), GREEN)
    bg = ACCENT_BACKGROUNDS.get(_tone(tone), "#E8F5EE")
    hint_html = f'<div class="np-progress-note">{escape(hint)}</div>' if hint else ""
    _html(
        f'<div class="np-progress-wrap" style="border-left:4px solid {color};'
        f'background:{bg};">'
        f'<div class="np-progress-meta"><span>{escape(label)}</span>'
        f"<strong>{escape(value)}</strong></div>{hint_html}</div>"
    )


def bmi_indicator(bmi: float, category: Optional[str] = None) -> None:
    """Render a live BMI indicator with a plain-language category."""
    value = float(bmi)
    if value < 18.5:
        tone, derived = "amber", "Underweight"
    elif value < 25:
        tone, derived = "green", "Healthy range"
    elif value < 30:
        tone, derived = "orange", "Overweight"
    else:
        tone, derived = "red", "Needs attention"
    display_category = str(category or derived)
    color = ACCENTS[tone]
    bg = ACCENT_BACKGROUNDS[tone]
    _html(
        f'<div class="np-callout" style="--np-accent:{color};--np-callout-bg:{bg};">'
        f"BMI <strong>{value:.1f}</strong> · {escape(display_category)} "
        f"· healthy range 18.5–24.9</div>"
    )


# ── Meal cards ────────────────────────────────────────────────────────────────

def meal_card(
    day_info: Mapping[str, Any],
    slot: str,
    config: Mapping[str, Any],
    serving_text_fn,
) -> None:
    """Render one visually accented meal card from an existing plan day."""
    meals = day_info.get("meals") or {}
    meal = (meals.get(slot) or {}) if isinstance(meals, dict) else {}
    items = [item for item in (meal.get("items") or []) if isinstance(item, dict)]
    calories = _num(meal.get("total_calories"))
    color = MEAL_ACCENTS.get(slot, GREEN)

    with st.container(border=True):
        _html(f'<div class="np-meal-accent" style="--np-accent:{color};"></div>')
        left, right = st.columns([4, 1.2], gap="small")
        with left:
            st.markdown(
                f"**{escape(str(config.get('icon', '🍽️')))} "
                f"{escape(str(config.get('label', slot.title())))}**"
            )
            st.caption(str(config.get("time", "")))
        with right:
            _html(
                f'<div class="np-meal-calories">{calories:.0f}'
                f"<span>kcal</span></div>"
            )

        if items:
            lines = []
            for item in items:
                name = escape(str(item.get("food_name", "Food")))
                serving = escape(str(serving_text_fn(item)))
                item_cal = _num(item.get("calories"))
                lines.append(
                    f"- **{name}** — {serving} · {item_cal:.0f} kcal"
                )
            st.markdown("\n".join(lines))
            st.caption(
                f"Protein {_num(meal.get('total_protein')):.1f} g · "
                f"Carbs {_num(meal.get('total_carbs')):.1f} g · "
                f"Fats {_num(meal.get('total_fat')):.1f} g · "
                f"Fibre {_num(meal.get('total_fiber')):.1f} g"
            )
        else:
            st.caption("Nothing planned for this meal.")

        swaps = ", ".join(str(x) for x in (config.get("alternatives") or [])[:4])
        st.caption(f"Swap ideas: {swaps}" if swaps else "Swap ideas: ask the AI nutritionist.")


# ── Tables and states ─────────────────────────────────────────────────────────

def nutrition_table(
    frame: pd.DataFrame,
    alt: str,
    column_config: Optional[dict[str, Any]] = None,
    height: Optional[int] = None,
) -> None:
    """Render a wide, readable dataframe with an accessible name."""
    kwargs: dict[str, Any] = {
        "hide_index": True,
        "width": "stretch",
        "column_config": column_config,
        "alt": alt,
    }
    # Streamlit >= 1.50 rejects height=None; only forward an explicit height.
    if height is not None:
        kwargs["height"] = height
    st.dataframe(frame, **kwargs)


def empty_state(
    title: str,
    message: str,
    icon: str = "🍱",
    action_label: Optional[str] = None,
    on_action: Optional[Any] = None,
    key: Optional[str] = None,
) -> None:
    """Render a friendly empty state with an optional action button."""
    _html(
        f'<div class="np-empty"><div class="np-empty-icon">{escape(icon)}</div>'
        f"<h3>{escape(title)}</h3><p>{escape(message)}</p></div>"
    )
    if action_label and on_action:
        st.button(
            action_label,
            type="primary",
            key=key,
            on_click=on_action,
        )


def error_message(message: str) -> None:
    """Render a consistent error message."""
    st.error(message)


def callout(message: str, tone: str = "green", icon: str = "💡") -> None:
    """Render a coloured informational callout."""
    color = ACCENTS.get(_tone(tone), GREEN)
    bg = ACCENT_BACKGROUNDS.get(_tone(tone), "#E8F5EE")
    _html(
        f'<div class="np-callout" style="--np-accent:{color};--np-callout-bg:{bg};">'
        f"{escape(icon)} {escape(message)}</div>"
    )


def source_note(text: str) -> None:
    """Render a small provenance note."""
    _html(f'<div class="np-source-note">{escape(text)}</div>')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "ACCENTS",
    "GREEN",
    "RED",
    "bmi_indicator",
    "badge",
    "callout",
    "empty_state",
    "error_message",
    "meal_card",
    "metric_card",
    "nutrition_table",
    "progress_bar",
    "render_badges",
    "section_header",
    "source_note",
    "stat_tile",
    "status_badge",
]
