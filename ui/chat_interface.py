"""
ui/chat_interface.py
--------------------
Modern AI nutritionist chat page.

The conversation is rendered with native Streamlit chat elements and the answer
still comes from the existing LangGraph agent via ``app_graph.invoke``.  RAG
answer text, citations, vector-distance footers and irrelevant-query notices are
displayed exactly as produced by the backend — this module never rewrites them.
"""

from __future__ import annotations

from html import escape
from typing import Any, Optional

import streamlit as st
from langchain_core.messages import HumanMessage

from agent.graph import app_graph
from ui.components import section_header, source_note
from ui.layout import render_chat_hero


# Short button label -> full question sent to the assistant.
#
# NOTE: in offline mode the agent answers meal-keyword questions from the local
# food database *before* it consults the RAG knowledge base.  "ICMR-NIN facts"
# is therefore a dedicated, non-meal question so it reliably exercises RAG and
# shows the cited answer/excerpts/sources trail.  "My numbers" deliberately
# avoids the word "explain ... nutritional" because that phrasing matched an
# unrelated fibre chunk in FAISS and hid the user's real target breakdown.
SUGGESTED_PROMPTS = {
    "Breakfast": "What should I take for morning breakfast?",
    "Lunch swap": "Suggest an alternative for afternoon lunch.",
    "Snacks": "What healthy snacks can I take in the evening?",
    "Protein dinner": "Suggest a high-protein dinner option.",
    "My numbers": "Show my calorie and macro breakdown",
    "ICMR-NIN facts": "What are the nutritional benefits of millets?",
}


def _history_key(thread_id: str) -> str:
    return f"chat_history_{thread_id or 'default'}"


def _welcome_message() -> dict[str, str]:
    return {
        "role": "assistant",
        "content": (
            "Namaste! I am your AI nutritionist. I can see your profile, daily "
            "targets and current meal plan. Ask me why a meal was chosen, request "
            "an alternative, or ask a general Indian nutrition question."
        ),
    }


def _get_history(thread_id: str) -> list[dict[str, str]]:
    key = _history_key(thread_id)
    history = st.session_state.get(key)
    if not isinstance(history, list):
        history = [_welcome_message()]
        st.session_state[key] = history
    return history


def _context_line(
    user_profile: Optional[dict[str, Any]],
    nutrition_targets: Optional[dict[str, Any]],
    weekly_plan: Optional[dict[str, Any]],
) -> None:
    profile = user_profile or {}
    targets = nutrition_targets or {}
    bits: list[str] = []
    if profile.get("name"):
        bits.append(str(profile["name"]))
    bits.append(
        "vegetarian" if profile.get("diet_type", "veg") == "veg" else "non-vegetarian"
    )
    if profile.get("allergies"):
        bits.append("allergy: " + ", ".join(str(item) for item in profile["allergies"]))
    if targets.get("calorie_target"):
        bits.append(f"{float(targets['calorie_target']):,.0f} kcal/day")
    plan_ready = bool(isinstance(weekly_plan, dict) and weekly_plan.get("days"))
    bits.append("plan ready" if plan_ready else "no plan yet")
    st.caption("🧠 Knows: " + " · ".join(bits))

    badges: list[dict[str, str]] = [
        {"label": str(profile.get("name", "Active user")), "tone": "green", "icon": "👤"},
        {
            "label": "Veg" if profile.get("diet_type", "veg") == "veg" else "Non-veg",
            "tone": "teal",
            "icon": "🌱",
        },
    ]
    if targets.get("calorie_target"):
        badges.append(
            {
                "label": f"{float(targets['calorie_target']):,.0f} kcal target",
                "tone": "orange",
                "icon": "🔥",
            }
        )
    badges.append(
        {
            "label": "Plan ready" if plan_ready else "No plan yet",
            "tone": "blue" if plan_ready else "amber",
            "icon": "✅" if plan_ready else "⏳",
        }
    )
    st.markdown(
        '<div class="np-chat-context">'
        + "".join(
            f'<span class="np-badge np-badge--{item["tone"]}">'
            f'{escape(item["icon"])} {escape(item["label"])}</span>'
            for item in badges
        )
        + "</div>",
        unsafe_allow_html=True,
    )


def _ask(
    prompt: str,
    thread_id: str,
    history_key: str,
    history: list[dict[str, str]],
    user_profile: Optional[dict[str, Any]],
    nutrition_targets: Optional[dict[str, Any]],
) -> None:
    """Send a chat turn to the existing LangGraph agent and store the answer."""
    history.append({"role": "user", "content": prompt})
    st.session_state[history_key] = history

    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Checking your plan and ICMR-NIN guidance..."):
            st.markdown(
                '<div class="np-typing"><i></i><i></i><i></i> '
                "AI Nutrition Planner is thinking…</div>",
                unsafe_allow_html=True,
            )
            try:
                result = app_graph.invoke(
                    {
                        "messages": [HumanMessage(content=prompt)],
                        "user_profile": user_profile,
                        "nutrition_targets": nutrition_targets,
                    },
                    config={"configurable": {"thread_id": thread_id}},
                )
                response = result.get("final_response")
                if not response:
                    messages = result.get("messages") or []
                    response = getattr(messages[-1], "content", "") if messages else ""
                if not isinstance(response, str):
                    response = str(response)
                if not response.strip():
                    response = "I could not answer that one. Try asking in a different way."
            except Exception as exc:
                response = f"Sorry, the assistant hit an error: {exc}"

        # Preserve the exact RAG formatting returned by the backend.
        st.markdown(response)

    history.append({"role": "assistant", "content": response})
    st.session_state[history_key] = history


def render_chat_interface(
    thread_id: str,
    user_profile: Optional[dict[str, Any]] = None,
    nutrition_targets: Optional[dict[str, Any]] = None,
    weekly_plan: Optional[dict[str, Any]] = None,
) -> None:
    """Render the standalone AI nutritionist chat."""
    render_chat_hero(
        "Ask the AI nutritionist",
        "Personalised meal help, Indian nutrition guidance and cited ICMR-NIN answers.",
    )

    header_left, header_right = st.columns([4, 1])
    with header_right:
        if st.button("🧹 Clear chat", width="stretch", key="clear_chat_btn"):
            st.session_state[_history_key(thread_id)] = [_welcome_message()]
            st.rerun()

    _context_line(user_profile, nutrition_targets, weekly_plan)

    history_key = _history_key(thread_id)
    history = _get_history(thread_id)

    for message in history:
        role = message.get("role", "assistant")
        with st.chat_message(role, avatar="🤖" if role == "assistant" else "👤"):
            st.markdown(message.get("content", ""))

    st.write("")
    section_header(
        "Try a prompt",
        subtitle="Tap a chip or type your own question below.",
        icon="💬",
        level=5,
    )
    quick_prompt: Optional[str] = None
    chip_columns = st.columns(len(SUGGESTED_PROMPTS))
    for index, (label, prompt) in enumerate(SUGGESTED_PROMPTS.items()):
        with chip_columns[index]:
            if st.button(label, key=f"chat_chip_{index}", width="stretch"):
                quick_prompt = prompt

    typed_prompt = st.chat_input("Ask about your plan or Indian nutrition...")
    prompt = quick_prompt or typed_prompt

    if prompt:
        _ask(
            prompt=prompt,
            thread_id=thread_id,
            history_key=history_key,
            history=history,
            user_profile=user_profile,
            nutrition_targets=nutrition_targets,
        )

    source_note(
        "Answers may use your current plan plus the local ICMR-NIN knowledge "
        "base. Supporting excerpts, sources and vector-distance details are "
        "shown whenever retrieval succeeded."
    )
    st.caption("General guidance only. Not medical advice.")


__all__ = ["SUGGESTED_PROMPTS", "render_chat_interface"]
