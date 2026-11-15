"""
app.py
------
AI-Based Food and Nutrition Planning Agent
Main Streamlit Application Entry Point.

Combines:
- Streamlit Web Interface
- Pydantic User Profile Validation
- Mifflin-St Jeor & TDEE Calculations
- 5 Python Tools
- Google Gemini 2.0 Flash Reasoning
- LangGraph 7-Node Agent Workflow
- ICMR-NIN Indian Food Composition Database
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
from ui.profile_form import render_profile_form


# ── Page Configuration ────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI Food & Nutrition Planning Agent",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for Polished Look ──────────────────────────────────────────────

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        font-size: 0.8rem;
        font-weight: 600;
        border-radius: 9999px;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }
    .badge-primary { background-color: #E0E7FF; color: #3730A3; }
    .badge-success { background-color: #D1FAE5; color: #065F46; }
    .badge-warning { background-color: #FEF3C7; color: #92400E; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Session State Initialization ──────────────────────────────────────────────

def _init_session_state() -> None:
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "user_profile": None,
        "nutrition_targets": None,
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


# ── Cached Food Dataset Loader ────────────────────────────────────────────────

@st.cache_data
def load_cached_food_data() -> pd.DataFrame:
    """Load food database once and cache in Streamlit memory."""
    return _get_df()


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🥗 AI Food Planner")
    st.caption("Personalized Indian Nutrition using Agentic AI")
    st.caption(f"⚡ Reasoning Engine: `{settings.model_name}`")

    # Render User Profile Form
    profile_data = render_profile_form()

    if profile_data:
        # Trigger Meal Plan Generation Workflow
        with st.spinner("🤖 Agent is analyzing targets and generating meal plan..."):
            try:
                # Update session thread
                st.session_state.thread_id = str(uuid.uuid4())
                st.session_state.user_profile = profile_data

                # Precompute targets immediately for fast dashboard render
                p_obj = UserProfile(**profile_data)
                targets_obj = calculate_nutrition_targets(p_obj)
                st.session_state.nutrition_targets = targets_obj.model_dump()

                # Run LangGraph Workflow
                config = {"configurable": {"thread_id": st.session_state.thread_id}}
                initial_state = {
                    "user_profile": profile_data,
                    "messages": [],
                    "revision_count": 0,
                }
                result = app_graph.invoke(initial_state, config=config)

                # Store outputs in state
                if result.get("nutrition_targets"):
                    st.session_state.nutrition_targets = result["nutrition_targets"]
                if result.get("meal_plan"):
                    st.session_state.meal_plan = result["meal_plan"]
                if result.get("validation_result"):
                    st.session_state.validation_result = result["validation_result"]
                if result.get("final_response"):
                    st.session_state.agent_explanation = result["final_response"]

                st.success("🎉 Personalized meal plan generated!")
            except Exception as e:
                st.error(f"Error during agent execution: {e}")

    st.divider()
    st.markdown("### 📚 Data Source")
    st.caption("Indian Food Composition Tables (IFCT) — ICMR-National Institute of Nutrition (NIN).")


# ── Main Content Area ─────────────────────────────────────────────────────────

st.markdown('<div class="main-title">🥗 AI-Based Food & Nutrition Planning Agent</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    'Autonomous Agentic AI that calculates precise caloric targets, searches curated Indian foods, '
    'assembles 4-meal daily plans, and self-validates dietary compliance.'
    '</div>',
    unsafe_allow_html=True,
)

# Badges
st.markdown(
    """
    <span class="badge badge-primary">⚡ Google Gemini 2.0 Flash</span>
    <span class="badge badge-success">🧠 LangGraph 7-Node Architecture</span>
    <span class="badge badge-warning">🍛 ICMR-NIN Indian Food Dataset (57 items)</span>
    <span class="badge badge-primary">🔍 Local RAG (FAISS + MiniLM-L6-v2)</span>
    """,
    unsafe_allow_html=True,
)

# Tab Navigation
tab_plan, tab_chat, tab_data, tab_about = st.tabs(
    ["🍱 Meal Plan & Dashboard", "💬 AI Nutritionist Chat", "🔍 Food Database", "⚙️ System Architecture"]
)

# ── Tab 1: Meal Plan & Dashboard ──────────────────────────────────────────────
with tab_plan:
    if st.session_state.get("nutrition_targets"):
        render_nutrition_dashboard(
            targets=st.session_state.get("nutrition_targets"),
            meal_plan=st.session_state.get("meal_plan"),
            validation_result=st.session_state.get("validation_result"),
        )

        if st.session_state.get("agent_explanation"):
            st.divider()
            st.markdown("### 📝 AI Nutritionist Rationale & Advice")
            st.markdown(st.session_state.get("agent_explanation"))
    else:
        st.info("👈 Please fill out your profile in the sidebar and click **'Generate Meal Plan'** to begin.")
        # Show sample preview with default calculation
        sample_p = UserProfile(
            name="Sample",
            age=28,
            gender="male",
            height_cm=175.0,
            weight_kg=75.0,
            activity_level="moderately_active",
            fitness_goal="weight_loss",
            diet_type="veg",
        )
        sample_targets = calculate_nutrition_targets(sample_p).model_dump()
        st.markdown("#### Sample Preview (28y Male, 75kg, Moderately Active, Weight Loss):")
        render_nutrition_dashboard(targets=sample_targets)

# ── Tab 2: AI Nutritionist Chat ───────────────────────────────────────────────
with tab_chat:
    render_chat_interface(
        thread_id=st.session_state.get("thread_id", ""),
        user_profile=st.session_state.get("user_profile"),
        nutrition_targets=st.session_state.get("nutrition_targets"),
    )

# ── Tab 3: Food Database Explorer ─────────────────────────────────────────────
with tab_data:
    st.markdown("### 🔍 Indian Food Database (ICMR-NIN Curated)")
    st.caption("Explore nutritional information per 100g for all 57 verified Indian food items.")

    df_all = load_cached_food_data()

    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        search_query = st.text_input("Filter by Food Name", "")
    with col_f2:
        diet_filter = st.selectbox("Diet Type", ["all", "veg", "non-veg"])
    with col_f3:
        cat_filter = st.selectbox("Category", ["all"] + sorted(df_all["food_category"].unique().tolist()))

    filtered_df = df_all.copy()
    if search_query:
        filtered_df = filtered_df[filtered_df["food_name"].str.contains(search_query, case=False, na=False)]
    if diet_filter != "all":
        filtered_df = filtered_df[filtered_df["diet_type"] == diet_filter]
    if cat_filter != "all":
        filtered_df = filtered_df[filtered_df["food_category"] == cat_filter]

    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
    )
    st.caption(f"Showing {len(filtered_df)} of {len(df_all)} food items.")

# ── Tab 4: System Architecture ────────────────────────────────────────────────
with tab_about:
    st.markdown("### ⚙️ System Architecture & Workflow")
    st.markdown(
        """
        The **AI-Based Food & Nutrition Planning Agent** operates via a 7-stage workflow combining:
        - **Biometrics & Energy Math**: Mifflin-St Jeor formula for BMR, adjusted for Physical Activity Level (PAL) and fitness goals.
        - **6 Specialized Tools**: Direct computation, vectorised food search, macro math, cosine similarity substitutions, deterministic constraint verification, and local RAG nutrition document retrieval.
        - **Retrieval-Augmented Generation (RAG)**: Dense vector similarity search over authoritative ICMR-NIN dietary guidelines using local HuggingFace embeddings (`all-MiniLM-L6-v2`) and a persistent FAISS index.
        - **Gemini 2.0 Flash + LangGraph**: Agentic decision-making, autonomous tool invocation, and self-correction loop.
        - **Self-Healing Loop**: If a proposed meal plan violates calorie limits (±15%), contains forbidden allergens, or violates diet types, the **Plan Revision** node detects issues and prompts the agent to correct itself (maximum 2 retries).
        """
    )
    st.code(
        """
User Profile Form (Streamlit)
        │
        ▼
Profile Validation Node (Pydantic v2)
        │
        ▼
Nutrition Calculation Node (Mifflin-St Jeor & TDEE)
        │
        ▼
Gemini 2.0 Flash Agent ◄────────────────┐
        │                               │
        ├──────(calls tool)─────► Tool Execution (5 Tools)
        │
        ▼
Meal Plan Validation Node (Deterministic Rule Engine)
        │
        ├──────(Pass)───────────────────► Final Response ──► Streamlit UI
        │
        └──────(Fail, retries < 2)──────► Plan Revision Node ──► Agent
        """,
        language="text",
    )
