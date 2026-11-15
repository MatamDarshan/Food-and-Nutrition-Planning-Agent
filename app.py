"""
app.py
------
AI-Based Food and Nutrition Planning Agent
Main Streamlit Application Entry Point.

Architecture:
- Page 1: User Profile & Goals
- Page 2: Nutrition Dashboard
- Page 3: 7-Day Meal Planner
- Page 4: Food Database Explorer
- Page 5: AI Nutritionist Chat Assistant

Technologies:
- Python 3.10+, Streamlit, LangGraph, Gemini 2.0 Flash, FAISS, HuggingFace embeddings
- ICMR-NIN Indian Food Composition Tables (IFCT 2017) & RDA 2020
"""

import os
import uuid
import pandas as pd
import streamlit as st

from agent.graph import app_graph
from config.settings import settings
from core.calculations import calculate_nutrition_targets
from core.user_profile import UserProfile
from tools.food_tools import _get_df
from ui.chat_interface import render_chat_interface
from ui.dashboard import render_nutrition_dashboard
from ui.food_database import render_food_database_page
from ui.meal_planner import render_7day_meal_planner
from ui.profile_form import render_profile_form
from ui.styles import THEME_CSS


# ── Page Configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Food & Nutrition Planning Agent",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply Modern Theme CSS
st.markdown(THEME_CSS, unsafe_allow_html=True)


# ── Session State Initialization ──────────────────────────────────────────────

def _init_session_state() -> None:
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "active_nav": "🍱 7-Day Meal Planner",
        "user_profile": None,
        "nutrition_targets": None,
        "weekly_plan": None,
        "meal_plan": None,
        "validation_result": None,
        "agent_explanation": "",
    }
    for k, v in defaults.items():
        if getattr(st.session_state, k, None) is None:
            try:
                st.session_state[k] = v
            except Exception:
                pass

_init_session_state()


# ── Auto-Initialize Default Profile & Plan for Seamless First Impression ─────

def _ensure_initial_plan() -> None:
    """Provide an initial default plan so the user immediately sees a rich 7-day dashboard."""
    if st.session_state.get("weekly_plan") is None and st.session_state.get("user_profile") is None:
        default_profile = {
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
        try:
            p_obj = UserProfile(**default_profile)
            targets_obj = calculate_nutrition_targets(p_obj)
            st.session_state.user_profile = default_profile
            st.session_state.nutrition_targets = targets_obj.model_dump()

            config = {"configurable": {"thread_id": st.session_state.thread_id}}
            init_state = {
                "user_profile": default_profile,
                "nutrition_targets": st.session_state.nutrition_targets,
                "messages": [],
                "revision_count": 0,
            }
            res = app_graph.invoke(init_state, config=config)
            if res.get("weekly_plan"):
                st.session_state.weekly_plan = res["weekly_plan"]
            if res.get("meal_plan"):
                st.session_state.meal_plan = res["meal_plan"]
            if res.get("validation_result"):
                st.session_state.validation_result = res["validation_result"]
            if res.get("final_response"):
                st.session_state.agent_explanation = res["final_response"]
        except Exception:
            pass

_ensure_initial_plan()


# ── Sidebar Navigation & Branding ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🌿 AI Food Planner")
    st.caption("Personalized Indian Nutrition & 7-Day Planning")

    # Engine status pill
    if settings.api_key:
        st.markdown(
            f"""
            <div style="background-color: #D8F3DC; border: 1px solid #74C69D; border-radius: 6px; padding: 0.35rem 0.6rem; font-size: 0.78rem; color: #1B4332; margin-bottom: 0.8rem;">
                ⚡ <strong>Active Engine:</strong> Google Gemini 2.0 Flash
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div style="background-color: #FEF3C7; border: 1px solid #FCD34D; border-radius: 6px; padding: 0.35rem 0.6rem; font-size: 0.78rem; color: #92400E; margin-bottom: 0.8rem;">
                💡 <strong>Offline Planner Active:</strong> ICMR-NIN Planning Engine
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Clean Navigation Radio
    nav_options = [
        "🍱 7-Day Meal Planner",
        "📊 Nutrition Dashboard",
        "👤 User Profile",
        "🔍 Food Database",
        "💬 AI Nutritionist Chat",
    ]

    current_nav = st.session_state.get("active_nav", "🍱 7-Day Meal Planner")
    if current_nav not in nav_options:
        current_nav = "🍱 7-Day Meal Planner"

    selected_nav = st.radio(
        "Navigation Menu",
        options=nav_options,
        index=nav_options.index(current_nav),
        label_visibility="collapsed",
    )
    st.session_state.active_nav = selected_nav

    st.divider()

    # Active Profile Summary Widget
    prof = st.session_state.get("user_profile")
    if prof:
        st.markdown("##### 👤 Current User")
        st.markdown(f"**Name:** {prof.get('name', 'Arjun')}")
        st.markdown(f"**Diet:** {prof.get('diet_type', 'veg').upper()}")
        st.markdown(f"**Goal:** {prof.get('fitness_goal', 'weight_loss').replace('_', ' ').title()}")
        allergies_list = prof.get("allergies", [])
        if allergies_list:
            st.markdown(f"**Allergies:** {', '.join(allergies_list)}")
        excluded_list = prof.get("excluded_foods", [])
        if excluded_list:
            st.markdown(f"**Excluded:** {', '.join(excluded_list)}")

    st.divider()
    st.markdown("##### 📚 Reference Standard")
    st.caption("Indian Food Composition Tables (IFCT 2017) & Recommended Dietary Allowances (RDA 2020) — ICMR-NIN, Hyderabad.")


# ── Main Content Header ───────────────────────────────────────────────────────

st.markdown(
    """
    <div style="margin-bottom: 1.25rem;">
        <h2 style="margin: 0; color: #1B4332; font-weight: 700;">🌿 AI-Based Food and Nutrition Planning Agent</h2>
        <p style="margin-top: 0.25rem; font-size: 0.95rem; color: #4B5563;">
            Autonomous Agentic AI that computes personalized biometric energy requirements, searches curated Indian foods,
            assembles balanced 7-day meal plans, and deterministicly verifies dietary safety.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Page Routing ──────────────────────────────────────────────────────────────

active_page = st.session_state.active_nav

if active_page == "👤 User Profile":
    st.markdown("### 👤 User Profile & Goal Configuration")
    profile_data = render_profile_form()

    if profile_data:
        with st.spinner("🤖 AI Agent is computing biometric energy targets and assembling a 7-day meal plan..."):
            try:
                st.session_state.thread_id = str(uuid.uuid4())
                st.session_state.user_profile = profile_data

                # Precompute targets
                p_obj = UserProfile(**profile_data)
                targets_obj = calculate_nutrition_targets(p_obj)
                st.session_state.nutrition_targets = targets_obj.model_dump()

                # Run LangGraph Workflow
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                init_state = {
                    "user_profile": profile_data,
                    "nutrition_targets": st.session_state.nutrition_targets,
                    "messages": [],
                    "revision_count": 0,
                }
                res = app_graph.invoke(init_state, config=config)

                if res.get("weekly_plan"):
                    st.session_state.weekly_plan = res["weekly_plan"]
                if res.get("meal_plan"):
                    st.session_state.meal_plan = res["meal_plan"]
                if res.get("validation_result"):
                    st.session_state.validation_result = res["validation_result"]
                if res.get("final_response"):
                    st.session_state.agent_explanation = res["final_response"]

                st.session_state.active_nav = "🍱 7-Day Meal Planner"
                st.rerun()
            except Exception as e:
                st.error(f"Error during plan generation: {e}")

elif active_page == "📊 Nutrition Dashboard":
    render_nutrition_dashboard(
        targets=st.session_state.get("nutrition_targets"),
        meal_plan=st.session_state.get("meal_plan"),
        validation_result=st.session_state.get("validation_result"),
    )

elif active_page == "🍱 7-Day Meal Planner":
    render_7day_meal_planner(
        weekly_plan=st.session_state.get("weekly_plan"),
        targets=st.session_state.get("nutrition_targets"),
        validation_result=st.session_state.get("validation_result"),
    )

elif active_page == "🔍 Food Database":
    render_food_database_page()

elif active_page == "💬 AI Nutritionist Chat":
    render_chat_interface(
        thread_id=st.session_state.get("thread_id", ""),
        user_profile=st.session_state.get("user_profile"),
        nutrition_targets=st.session_state.get("nutrition_targets"),
        weekly_plan=st.session_state.get("weekly_plan"),
    )
