"""
app.py
------
AI-Based Food and Nutrition Planning Agent — Streamlit entry point.

Pages (deliberately short labels):
1. 🍽️ Today    — today's calories, timetable and four meal cards.
2. 📅 My week  — a compact week table, then any day in detail.
3. 👤 My profile — create or edit a profile, see calculated targets.
4. 🥗 Food data — search the ICMR-NIN food composition tables.
5. 🤖 Ask AI   — a separate nutritionist chat page.
"""

import logging
import sys

# Streamlit's file watcher introspects every imported module for hot reloading.
# `transformers` eagerly exposes optional image processors that import
# `torchvision`, which is not installed and is not needed by the text-only RAG
# embedding model.  The resulting "ModuleNotFoundError: No module named
# 'torchvision'" tracebacks flood the server log and look like a RAG failure.
# Silence only that watcher logger so genuine RAG errors still surface.
logging.getLogger("streamlit.watcher.local_sources_watcher").setLevel(logging.ERROR)

# ── Windows Asyncio Socket Shutdown Guard (WinError 10054) ────────────────────
if sys.platform.startswith("win"):
    import asyncio

    try:
        from asyncio.proactor_events import _ProactorBasePipeTransport

        _orig_call_connection_lost = _ProactorBasePipeTransport._call_connection_lost

        def _safe_call_connection_lost(self, exc):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError) as e:
                if getattr(e, "winerror", None) == 10054 or "10054" in str(e):
                    pass
                else:
                    raise

        _ProactorBasePipeTransport._call_connection_lost = _safe_call_connection_lost
    except Exception:
        pass

import uuid
from typing import Any, Optional

import streamlit as st

from agent.graph import app_graph
from config.settings import settings
from core.calculations import calculate_nutrition_targets
from core.user_profile import UserProfile
from ui.chat_interface import render_chat_interface
from ui.dashboard import render_targets_panel
from ui.food_database import render_food_database_page
from ui.layout import render_sidebar
from ui.meal_planner import render_today_page, render_week_page
from ui.profile_form import blank_profile, render_profile_form
from ui.styles import THEME_CSS


# ── Page configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Food & Nutrition Planner",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(THEME_CSS, unsafe_allow_html=True)


# ── Pages ─────────────────────────────────────────────────────────────────────

PAGE_TODAY = "🍽️ Today"
PAGE_WEEK = "📅 My week"
PAGE_PROFILE = "👤 My profile"
PAGE_FOOD_DB = "🥗 Food data"
PAGE_CHAT = "🤖 Ask AI"

PAGES = [PAGE_TODAY, PAGE_WEEK, PAGE_PROFILE, PAGE_FOOD_DB, PAGE_CHAT]

DEFAULT_PROFILE: dict[str, Any] = {
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
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _new_thread_id() -> str:
    return str(uuid.uuid4())


def _init_session_state() -> None:
    st.session_state.setdefault("users", {})
    st.session_state.setdefault("current_user_name", DEFAULT_PROFILE["name"])
    st.session_state.setdefault("active_nav", PAGE_TODAY)
    st.session_state.setdefault("nav_page", PAGE_TODAY)
    st.session_state.setdefault("thread_id", _new_thread_id())
    st.session_state.setdefault("profile_form_token", 0)
    st.session_state.setdefault("_new_user_mode", False)
    st.session_state.setdefault("_demo_attempted", False)
    st.session_state.setdefault("init_plan_error", None)
    st.session_state.setdefault("pending_page", None)


def _go(page: str) -> None:
    """Navigate programmatically, keeping the sidebar radio in sync.

    The radio is keyed, so its stored value must be written too. Passing a
    changing ``index`` instead would change the widget id and make the next
    click get ignored.
    """
    st.session_state.active_nav = page
    st.session_state.nav_page = page


def _apply_user_record(name: str, record: dict[str, Any]) -> None:
    """Store a user plan and make it the active session view in one place."""
    st.session_state.users[name] = record
    st.session_state.current_user_name = name
    st.session_state.user_profile = record.get("user_profile")
    st.session_state.nutrition_targets = record.get("nutrition_targets")
    st.session_state.weekly_plan = record.get("weekly_plan")
    st.session_state.meal_plan = record.get("meal_plan")
    st.session_state.validation_result = record.get("validation_result")
    st.session_state.agent_explanation = record.get("agent_explanation", "")
    st.session_state.thread_id = record.get("thread_id", _new_thread_id())
    st.session_state.form_draft = dict(record.get("user_profile") or {})
    st.session_state._form_draft_user = name
    # A new token recreates the profile widgets so they pick up this record's
    # values instead of showing the previous profile's stored widget state.
    st.session_state.profile_form_token = (
        int(st.session_state.get("profile_form_token", 0)) + 1
    )
    st.session_state._new_user_mode = False
    # A programmatic profile change must also move the keyed sidebar selector.
    # Without this flag the widget keeps its previous value and immediately
    # overwrites current_user_name on the next rerun.
    st.session_state._profile_switcher_sync = True


def _build_user_record(
    profile_data: dict[str, Any],
    thread_id: Optional[str] = None,
) -> dict[str, Any]:
    """Validate a profile, compute targets, run the agent, return a UI record."""
    profile_obj = UserProfile(**profile_data)
    profile_clean = profile_obj.model_dump()
    targets = calculate_nutrition_targets(profile_obj).model_dump()
    thread = thread_id or _new_thread_id()

    result = app_graph.invoke(
        {
            "user_profile": profile_clean,
            "nutrition_targets": targets,
            "messages": [],
            "revision_count": 0,
        },
        config={"configurable": {"thread_id": thread}},
    )

    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    if not result.get("weekly_plan") and not result.get("meal_plan"):
        raise RuntimeError("The planning engine did not return a meal plan.")

    return {
        "user_profile": profile_clean,
        "nutrition_targets": targets,
        "weekly_plan": result.get("weekly_plan"),
        "meal_plan": result.get("meal_plan"),
        "validation_result": result.get("validation_result"),
        "agent_explanation": result.get("final_response", ""),
        "thread_id": thread,
    }


def _generate_for_current_user() -> None:
    """Rebuild the active user's plan, surfacing failures instead of hiding them."""
    profile = st.session_state.get("user_profile")
    if not profile:
        st.error("Choose or create a profile before building a meal plan.")
        return
    name = profile.get("name", "User")
    with st.spinner(f"Building a fresh 7-day plan for {name}..."):
        try:
            record = _build_user_record(profile)
        except Exception as exc:
            st.error(f"Could not build the plan: {exc}")
            return
    _apply_user_record(name, record)
    st.toast(f"✅ New plan ready for {name}")


def _start_new_profile() -> None:
    _go(PAGE_PROFILE)
    st.session_state._new_user_mode = True
    st.session_state._form_draft_user = None
    st.session_state.profile_form_token += 1
    st.session_state.form_draft = blank_profile()


# ── Session bootstrap ─────────────────────────────────────────────────────────

_init_session_state()

# Page changes requested after the sidebar has rendered are applied on the next
# run, before the nav widget is created.
_pending_page = st.session_state.get("pending_page")
if _pending_page:
    st.session_state.pending_page = None
    if _pending_page in PAGES:
        _go(_pending_page)


def _ensure_demo_user() -> None:
    """Create a ready-to-explore demo user so the app never starts empty."""
    if st.session_state.users or st.session_state.get("_demo_attempted"):
        return
    st.session_state._demo_attempted = True
    with st.spinner("Preparing your sample plan..."):
        try:
            record = _build_user_record(DEFAULT_PROFILE, st.session_state.thread_id)
        except Exception as exc:
            st.session_state.init_plan_error = str(exc)
            return
    _apply_user_record(DEFAULT_PROFILE["name"], record)
    st.session_state.init_plan_error = None


_ensure_demo_user()


# ── Keep the active view in sync with the selected profile ────────────────────

current_name = st.session_state.get("current_user_name", DEFAULT_PROFILE["name"])
if current_name in st.session_state.users:
    record = st.session_state.users[current_name]
    st.session_state.user_profile = record.get("user_profile")
    st.session_state.nutrition_targets = record.get("nutrition_targets")
    st.session_state.weekly_plan = record.get("weekly_plan")
    st.session_state.meal_plan = record.get("meal_plan")
    st.session_state.validation_result = record.get("validation_result")
    st.session_state.agent_explanation = record.get("agent_explanation", "")
    st.session_state.thread_id = record.get("thread_id", st.session_state.thread_id)
    if (
        not st.session_state.get("_new_user_mode")
        and st.session_state.get("_form_draft_user") != current_name
    ):
        st.session_state.form_draft = dict(record.get("user_profile") or {})
        st.session_state._form_draft_user = current_name
        # Switching profiles must also rebuild the form widgets, otherwise the
        # fields keep showing the profile that was open before the switch.
        st.session_state.profile_form_token = (
            int(st.session_state.get("profile_form_token", 0)) + 1
        )


# ── Sidebar ───────────────────────────────────────────────────────────────────

render_sidebar(
    pages=PAGES,
    current_name=current_name,
    users=st.session_state.users,
    api_key=settings.api_key,
    model_name=settings.model_name,
    on_new_profile=_start_new_profile,
)


# ── Routing ───────────────────────────────────────────────────────────────────

active_page = st.session_state.active_nav
active_profile = st.session_state.get("user_profile") or {}
active_name = active_profile.get("name", current_name)

if st.session_state.get("init_plan_error"):
    st.warning(
        "The sample plan could not be built. You can still create your own "
        "profile. Details: " + str(st.session_state.init_plan_error)
    )


if active_page == PAGE_PROFILE:
    profile_data = render_profile_form(initial_profile=active_profile or DEFAULT_PROFILE)

    if profile_data:
        target_name = profile_data.get("name", "User")
        with st.spinner(f"Calculating targets and planning meals for {target_name}..."):
            try:
                record = _build_user_record(profile_data, _new_thread_id())
            except Exception as exc:
                st.error(f"Could not create the plan for {target_name}: {exc}")
            else:
                existed = target_name in st.session_state.users
                _apply_user_record(target_name, record)
                st.session_state.pending_page = PAGE_TODAY
                st.toast(
                    f"✅ {'Updated' if existed else 'Created'} {target_name}'s profile"
                )
                st.rerun()

    if st.session_state.get("nutrition_targets") and not st.session_state.get(
        "_new_user_mode"
    ):
        st.divider()
        render_targets_panel(
            st.session_state.get("nutrition_targets"),
            st.session_state.get("user_profile"),
        )

elif active_page == PAGE_TODAY:
    render_today_page(
        weekly_plan=st.session_state.get("weekly_plan"),
        targets=st.session_state.get("nutrition_targets"),
        validation_result=st.session_state.get("validation_result"),
        user_name=active_name,
        meal_plan=st.session_state.get("meal_plan"),
        on_generate=_generate_for_current_user,
        on_new_profile=_start_new_profile,
        user_profile=active_profile,
    )

elif active_page == PAGE_WEEK:
    render_week_page(
        weekly_plan=st.session_state.get("weekly_plan"),
        targets=st.session_state.get("nutrition_targets"),
        validation_result=st.session_state.get("validation_result"),
        user_name=active_name,
        meal_plan=st.session_state.get("meal_plan"),
        on_generate=_generate_for_current_user,
        on_new_profile=_start_new_profile,
        user_profile=active_profile,
    )

elif active_page == PAGE_FOOD_DB:
    render_food_database_page()

elif active_page == PAGE_CHAT:
    plan_thread = st.session_state.get("thread_id", "")
    render_chat_interface(
        thread_id=f"{plan_thread}:chat" if plan_thread else "chat",
        user_profile=st.session_state.get("user_profile"),
        nutrition_targets=st.session_state.get("nutrition_targets"),
        weekly_plan=st.session_state.get("weekly_plan"),
    )
